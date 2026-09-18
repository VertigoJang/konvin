#!/usr/bin/env python3
"""
Konvin 네트워크 라이브러리 — 같은 네트워크의 다른 Konvin 과 영상을 주고받는다.

konvin.py 가 이 모듈을 불러 "네트워크" 탭을 만든다. 실험용 CLI 였던
net_discover.py / net_library.py / net_transfer.py 의 내용을 GUI 에 맞게
옮겨 온 것이다.

동작 요약
    1. zeroconf 로 같은 네트워크의 Konvin 을 찾고, 나도 광고한다
    2. 각자 작은 HTTP 서버를 띄워 자기 영상 목록을 내준다
    3. 파일을 받으려면 상대에게 요청을 보내고, 상대가 허용해야 한다
    4. 허용되면 일회용 토큰이 나오고, 그걸로 파일을 받는다

승인 없이는 어떤 파일도 나가지 않는다. "이 컴퓨터는 항상 허용" 을 고르면
그 기기만 다음부터 묻지 않는다.
"""

import json
import secrets
import shutil
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

SERVICE_TYPE = "_konvin._tcp.local."

VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}

ASK_TIMEOUT = 60        # 확인 창을 몇 초 기다릴지
TOKEN_LIFETIME = 300    # 토큰이 몇 초 뒤 만료되는지
CHUNK = 256 * 1024


def zeroconf_available():
    """zeroconf 가 깔려 있는지. 없으면 네트워크 탭을 안내문으로 대체한다."""
    try:
        import zeroconf  # noqa: F401
        return True
    except ImportError:
        return False


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def local_ip():
    """바깥으로 나갈 때 쓰는 랜 주소. 실제로 연결하지는 않는다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ============================================
# 저장되는 것들
# ============================================

class TrustStore:
    """'항상 허용' 을 고른 기기를 기억한다."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.devices = self._load()

    def _load(self):
        if not self.path.exists():
            return {}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.devices, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def is_trusted(self, dev_id):
        with self.lock:
            return dev_id in self.devices

    def trust(self, dev_id, name):
        with self.lock:
            self.devices[dev_id] = {"name": name, "since": int(time.time())}
            self._save()

    def untrust(self, dev_id):
        with self.lock:
            gone = self.devices.pop(dev_id, None)
            self._save()

        return gone

    def listed(self):
        with self.lock:
            return [(k, dict(v)) for k, v in self.devices.items()]


class Library:
    """내줄 폴더를 훑어 목록을 만들고, id → 실제 경로 대응표를 들고 있는다.

    바깥에서 들어온 값을 파일 경로에 직접 쓰지 않으려는 장치다.
    """

    def __init__(self, folder):
        self.folder = Path(folder)
        self.by_id = {}
        self.lock = threading.Lock()

    def scan(self):
        items = []
        mapping = {}

        if self.folder.is_dir():
            for path in sorted(self.folder.iterdir()):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in VIDEO_SUFFIXES:
                    continue

                try:
                    stat = path.stat()
                except OSError:
                    continue

                file_id = uuid.uuid5(uuid.NAMESPACE_URL, path.name).hex[:12]
                mapping[file_id] = path
                items.append({
                    "id": file_id,
                    "title": path.stem,
                    "filename": path.name,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                })

        with self.lock:
            self.by_id = mapping

        return items

    def info_for(self, file_id):
        with self.lock:
            path = self.by_id.get(file_id)

        if not path or not path.is_file():
            return None

        try:
            return {"path": path, "size": path.stat().st_size}
        except OSError:
            return None


# ============================================
# 요청 관리
# ============================================

class RequestDesk(QObject):
    """들어온 요청을 붙들고, 사람이 허용할 때까지 기다린다.

    HTTP 스레드에서 호출되지만 화면에 묻는 일은 신호로 넘긴다.
    """

    asked = Signal(str, str, str, int)     # req_id, 상대 이름, 파일 이름, 크기
    settled = Signal(str, str)             # req_id, 결과

    def __init__(self, trust, parent=None):
        super().__init__(parent)
        self.trust = trust
        self.requests = {}
        self.tokens = {}
        self.lock = threading.Lock()

    def submit(self, peer_name, peer_id, file_id, filename, size):
        req_id = secrets.token_urlsafe(9)

        with self.lock:
            self.requests[req_id] = {
                "state": "대기",
                "token": None,
                "at": time.time(),
                "file_id": file_id,
            }

        if self.trust.is_trusted(peer_id):
            self._approve(req_id, file_id)
            self.settled.emit(req_id, f"{peer_name} → {filename} (자동 허용)")
            return req_id, "허용"

        # 화면 쪽에서 받아 확인 창을 띄운다
        self.asked.emit(req_id, peer_name, filename, size)

        return req_id, "대기"

    def decide(self, req_id, decision, peer_id=None, peer_name=""):
        """화면에서 사람이 고른 결과를 알려 준다."""
        if decision == "always" and peer_id:
            self.trust.trust(peer_id, peer_name)

        with self.lock:
            entry = self.requests.get(req_id)

            if not entry or entry["state"] != "대기":
                return

            file_id = entry["file_id"]

        if decision in ("yes", "always"):
            self._approve(req_id, file_id)
        else:
            with self.lock:
                if req_id in self.requests:
                    self.requests[req_id]["state"] = "거부"

    def _approve(self, req_id, file_id):
        token = secrets.token_urlsafe(24)

        with self.lock:
            self.tokens[token] = (file_id, time.time())

            if req_id in self.requests:
                self.requests[req_id]["state"] = "허용"
                self.requests[req_id]["token"] = token

    def status(self, req_id):
        with self.lock:
            entry = self.requests.get(req_id)

            if not entry:
                return {"state": "없음", "token": None}

            # 너무 오래 대기한 요청은 거부로 본다
            if entry["state"] == "대기" and time.time() - entry["at"] > ASK_TIMEOUT:
                entry["state"] = "거부"

            return {"state": entry["state"], "token": entry["token"]}

    def take_token(self, token):
        with self.lock:
            entry = self.tokens.pop(token, None)

        if not entry:
            return None

        file_id, issued = entry

        return None if time.time() - issued > TOKEN_LIFETIME else file_id

    def sweep(self):
        now = time.time()

        with self.lock:
            for t in [t for t, (_, at) in self.tokens.items()
                      if now - at > TOKEN_LIFETIME]:
                del self.tokens[t]

            for r in [r for r, e in self.requests.items()
                      if now - e["at"] > TOKEN_LIFETIME * 2]:
                del self.requests[r]


# ============================================
# HTTP 서버
# ============================================

class Handler(BaseHTTPRequestHandler):

    library = None
    desk = None
    my_name = ""
    my_id = ""
    notify = None       # 로그를 남기는 함수 (클래스 속성)

    protocol_version = "HTTP/1.1"

    def _say(self, message):
        """로그를 남긴다.

        notify 는 클래스 속성이라, self.notify 로 꺼내면 평범한 함수일 때
        메서드처럼 묶여 인자가 하나 더 붙는다. 클래스에서 꺼내 쓴다.
        """
        fn = type(self).notify

        if fn:
            fn(message)

    def log_message(self, fmt, *args):
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/videos":
            self._json({
                "device": {"name": self.my_name, "id": self.my_id},
                "videos": self.library.scan(),
            })
            return

        if self.path.startswith("/request/") and self.path.endswith("/status"):
            req_id = self.path[len("/request/"):-len("/status")]
            self._json(self.desk.status(req_id))
            return

        if self.path.startswith("/download/"):
            self._download(self.path[len("/download/"):])
            return

        self._json({"error": "없는 경로입니다"}, status=404)

    def _download(self, token):
        file_id = self.desk.take_token(token)

        if not file_id:
            self._json({"error": "토큰이 없거나 만료됐습니다"}, status=403)
            return

        info = self.library.info_for(file_id)

        if not info:
            self._json({"error": "파일을 찾을 수 없습니다"}, status=404)
            return

        path, size = info["path"], info["size"]

        self._say(f"보내는 중: {path.name} ({human_size(size)})")

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.end_headers()

        try:
            with path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile, length=CHUNK)
        except (OSError, BrokenPipeError, ConnectionResetError):
            self._say(f"전송이 끊겼습니다: {path.name}")
            return

        self._say(f"보냈습니다: {path.name}")

    def do_POST(self):
        if self.path != "/request":
            self._json({"error": "없는 경로입니다"}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return

        self.library.scan()
        info = self.library.info_for(body.get("file_id", ""))

        if not info:
            self._json({"error": "그런 파일이 없습니다"}, status=404)
            return

        req_id, state = self.desk.submit(
            body.get("name", "(이름 없음)"),
            body.get("id", ""),
            body.get("file_id", ""),
            info["path"].name,
            info["size"],
        )
        self._json({"request_id": req_id, "state": state})


# ============================================
# 서비스 (발견 + 서버)
# ============================================

class NetService(QObject):
    """앱이 켜져 있는 동안 계속 도는 네트워크 쪽 살림."""

    peers_changed = Signal()
    log = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, device_name, device_id, trust_path, parent=None):
        super().__init__(parent)

        self.library = Library(folder)
        self.trust = TrustStore(trust_path)
        self.desk = RequestDesk(self.trust, self)

        self.device_name = device_name
        self.device_id = device_id

        self.peers = {}
        self.lock = threading.Lock()

        self.zc = None
        self.info = None
        self.browser = None
        self.server = None
        self.port = None
        self.running = False

    # --- 시작 / 끝 ---

    def start(self):
        if self.running:
            return True

        try:
            from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
        except ImportError:
            self.failed.emit("zeroconf")
            return False

        self.library.scan()

        Handler.library = self.library
        Handler.desk = self.desk
        Handler.my_name = self.device_name
        Handler.my_id = self.device_id
        Handler.notify = self.log.emit

        try:
            self.server = ThreadingHTTPServer(("", 0), Handler)
        except OSError as e:
            self.failed.emit(str(e))
            return False

        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

        ip = local_ip()

        try:
            self.zc = Zeroconf()
            self.info = ServiceInfo(
                SERVICE_TYPE,
                f"{self.device_name}-{self.device_id[:8]}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(ip)],
                port=self.port,
                properties={
                    "name": self.device_name,
                    "id": self.device_id,
                    "ver": "4",
                },
            )
            self.zc.register_service(self.info)
            self.browser = ServiceBrowser(self.zc, SERVICE_TYPE, self)
        except Exception as e:
            self.failed.emit(str(e))
            self.stop()
            return False

        self.running = True
        self.log.emit(f"네트워크 시작 — {ip}:{self.port}")

        return True

    def stop(self):
        self.running = False

        if self.zc:
            try:
                if self.info:
                    self.zc.unregister_service(self.info)
                self.zc.close()
            except Exception:
                pass

        self.zc = None
        self.info = None
        self.browser = None

        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass

        self.server = None

        with self.lock:
            self.peers.clear()

    # --- zeroconf 가 부르는 자리 ---

    def _describe(self, zc, name):
        info = zc.get_service_info(SERVICE_TYPE, name, timeout=3000)

        if not info:
            return None

        props = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in info.properties.items()
            if k and v
        }
        addresses = [socket.inet_ntoa(a) for a in info.addresses]

        if not addresses:
            return None

        return {
            "name": props.get("name", "(이름 없음)"),
            "id": props.get("id", ""),
            "address": addresses[0],
            "port": info.port,
        }

    def add_service(self, zc, type_, name):
        found = self._describe(zc, name)

        if not found or found["id"] == self.device_id:
            return

        with self.lock:
            self.peers[name] = found

        self.peers_changed.emit()

    def remove_service(self, zc, type_, name):
        with self.lock:
            gone = self.peers.pop(name, None)

        if gone:
            self.peers_changed.emit()

    def update_service(self, zc, type_, name):
        pass

    def listed_peers(self):
        with self.lock:
            return list(self.peers.values())


# ============================================
# 내려받기 작업자
# ============================================

class Fetcher(QThread):
    """요청 → 승인 대기 → 받기. 화면이 멈추지 않게 따로 돈다."""

    progress = Signal(int, str)     # 퍼센트, 설명
    done = Signal(bool, str)        # 성공 여부, 메시지

    def __init__(self, peer, video, my_name, my_id, save_dir, parent=None):
        super().__init__(parent)
        self.peer = peer
        self.video = video
        self.my_name = my_name
        self.my_id = my_id
        self.save_dir = Path(save_dir)
        self._stop = False

    def cancel(self):
        self._stop = True

    def _json(self, path, payload=None, timeout=10):
        url = f"http://{self.peer['address']}:{self.peer['port']}{path}"
        data = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(url, data=data, headers=headers)

        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def run(self):
        video = self.video
        target = self.save_dir / video["filename"]

        if target.exists():
            self.done.emit(False, f"이미 같은 이름의 파일이 있습니다: {target.name}")
            return

        # 1) 요청
        try:
            reply = self._json("/request", {
                "file_id": video["id"],
                "name": self.my_name,
                "id": self.my_id,
            })
        except urllib.error.HTTPError as e:
            self.done.emit(False, f"요청이 거절됐습니다 ({e.code})")
            return
        except urllib.error.URLError as e:
            self.done.emit(False, f"연결하지 못했습니다: {e.reason}")
            return

        req_id = reply.get("request_id")

        # 2) 승인 기다리기
        self.progress.emit(0, "상대의 승인을 기다리는 중...")
        token = None
        waited = 0

        while waited < ASK_TIMEOUT + 10:
            if self._stop:
                self.done.emit(False, "취소했습니다.")
                return

            try:
                status = self._json(f"/request/{req_id}/status", timeout=5)
            except urllib.error.URLError as e:
                self.done.emit(False, f"상태를 확인하지 못했습니다: {e.reason}")
                return

            if status.get("state") == "허용":
                token = status.get("token")
                break

            if status.get("state") == "거부":
                self.done.emit(False, "상대가 거부했습니다.")
                return

            time.sleep(1)
            waited += 1

        if not token:
            self.done.emit(False, "응답이 없어 그만뒀습니다.")
            return

        # 3) 받기
        self.progress.emit(0, "받는 중...")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        expected = video["size"]
        got = 0

        url = f"http://{self.peer['address']}:{self.peer['port']}/download/{token}"

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                with tmp.open("wb") as f:
                    while True:
                        if self._stop:
                            f.close()
                            tmp.unlink(missing_ok=True)
                            self.done.emit(False, "취소했습니다.")
                            return

                        chunk = response.read(CHUNK)

                        if not chunk:
                            break

                        f.write(chunk)
                        got += len(chunk)

                        if expected:
                            percent = int(got / expected * 100)
                            self.progress.emit(
                                percent,
                                f"받는 중... {human_size(got)} / {human_size(expected)}",
                            )
        except urllib.error.HTTPError as e:
            tmp.unlink(missing_ok=True)
            self.done.emit(False, f"받지 못했습니다 ({e.code})")
            return
        except (urllib.error.URLError, OSError) as e:
            tmp.unlink(missing_ok=True)
            self.done.emit(False, f"받는 중 끊겼습니다: {e}")
            return

        if expected and got != expected:
            tmp.unlink(missing_ok=True)
            self.done.emit(False, f"크기가 다릅니다 (받은 {got}, 예상 {expected})")
            return

        try:
            tmp.replace(target)
        except OSError as e:
            self.done.emit(False, f"저장하지 못했습니다: {e}")
            return

        self.done.emit(True, f"다 받았습니다: {target.name}")


# ============================================
# 확인 창
# ============================================

class ApprovalDialog(QDialog):
    """상대가 파일을 요청했을 때 뜨는 창."""

    def __init__(self, parent, texts, peer_name, filename, size):
        super().__init__(parent)

        self.texts = texts
        self.decision = "no"

        self.setWindowTitle(texts["net_ask_title"])
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        head = QLabel(texts["net_ask_body"].format(peer=peer_name))
        head.setWordWrap(True)
        layout.addWidget(head)

        file_label = QLabel(f"<b>{filename}</b>  ({human_size(size)})")
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        self.always_box = QCheckBox(texts["net_ask_always"])
        layout.addWidget(self.always_box)

        warning = QLabel(texts["net_ask_warning"])
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b36b00;")
        layout.addWidget(warning)

        buttons = QDialogButtonBox()
        deny = buttons.addButton(texts["net_ask_deny"], QDialogButtonBox.RejectRole)
        allow = buttons.addButton(texts["net_ask_allow"], QDialogButtonBox.AcceptRole)
        allow.setDefault(True)

        deny.clicked.connect(self._deny)
        allow.clicked.connect(self._allow)
        layout.addWidget(buttons)

    def _allow(self):
        self.decision = "always" if self.always_box.isChecked() else "yes"
        self.accept()

    def _deny(self):
        self.decision = "no"
        self.reject()


# ============================================
# 네트워크 탭
# ============================================

class NetworkTab(QWidget):

    def __init__(self, parent, texts, service, save_dir):
        super().__init__(parent)

        self.texts = texts
        self.service = service
        self.save_dir = Path(save_dir)
        self.videos = []
        self.fetcher = None

        layout = QVBoxLayout(self)

        self.hint = QLabel(texts["net_hint"])
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: gray;")
        layout.addWidget(self.hint)

        body = QHBoxLayout()

        # --- 왼쪽: 발견된 컴퓨터 ---
        left = QVBoxLayout()
        left.addWidget(QLabel(texts["net_peers"]))

        self.peer_list = QListWidget()
        self.peer_list.setMaximumWidth(240)
        self.peer_list.currentRowChanged.connect(self._peer_selected)
        left.addWidget(self.peer_list)

        self.trusted_button = QPushButton(texts["net_trusted"])
        self.trusted_button.clicked.connect(self._open_trusted)
        left.addWidget(self.trusted_button)

        body.addLayout(left)

        # --- 오른쪽: 그 컴퓨터의 영상 ---
        right = QVBoxLayout()
        right.addWidget(QLabel(texts["net_videos"]))

        self.video_tree = QTreeWidget()
        self.video_tree.setColumnCount(2)
        self.video_tree.setHeaderLabels([texts["net_col_name"], texts["net_col_size"]])
        self.video_tree.setRootIsDecorated(False)
        self.video_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.video_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        right.addWidget(self.video_tree)

        action = QHBoxLayout()
        self.refresh_button = QPushButton(texts["net_refresh"])
        self.refresh_button.clicked.connect(self._load_videos)
        action.addWidget(self.refresh_button)

        self.fetch_button = QPushButton(texts["net_fetch"])
        self.fetch_button.clicked.connect(self._fetch)
        action.addWidget(self.fetch_button)

        self.cancel_button = QPushButton(texts["net_cancel"])
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        action.addWidget(self.cancel_button)

        action.addStretch()
        right.addLayout(action)

        body.addLayout(right, stretch=1)
        layout.addLayout(body)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status = QLabel(texts["net_idle"])
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        # --- 신호 연결 ---
        self.service.peers_changed.connect(self._reload_peers)
        self.service.desk.asked.connect(self._on_asked)
        self.service.desk.settled.connect(self._on_settled)
        self.service.log.connect(self.status.setText)
        self.service.failed.connect(self._on_failed)

        self._reload_peers()

    # --- 목록 ---

    def _reload_peers(self):
        current = self.peer_list.currentRow()
        peers = self.service.listed_peers()

        self.peer_list.clear()

        for p in peers:
            mark = f"  ({self.texts['net_trusted_mark']})" \
                if self.service.trust.is_trusted(p["id"]) else ""
            item = QListWidgetItem(f"{p['name']}{mark}")
            item.setData(Qt.UserRole, p)
            self.peer_list.addItem(item)

        if 0 <= current < self.peer_list.count():
            self.peer_list.setCurrentRow(current)

        if not peers:
            self.video_tree.clear()
            self.videos = []

    def _current_peer(self):
        item = self.peer_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _peer_selected(self, row):
        if row >= 0:
            self._load_videos()

    def _load_videos(self):
        peer = self._current_peer()

        self.video_tree.clear()
        self.videos = []

        if not peer:
            return

        url = f"http://{peer['address']}:{peer['port']}/videos"

        try:
            request = urllib.request.Request(
                url, headers={"Accept": "application/json"}
            )

            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            self.status.setText(
                self.texts["net_connect_failed"].format(error=e.reason)
            )
            return
        except Exception as e:
            self.status.setText(
                self.texts["net_connect_failed"].format(error=e)
            )
            return

        self.videos = payload.get("videos", [])

        for v in self.videos:
            item = QTreeWidgetItem([v["filename"], human_size(v["size"])])
            self.video_tree.addTopLevelItem(item)

        self.status.setText(
            self.texts["net_loaded"].format(
                peer=peer["name"], count=len(self.videos)
            )
        )

    # --- 받기 ---

    def _fetch(self):
        if self.fetcher and self.fetcher.isRunning():
            return

        peer = self._current_peer()
        index = self.video_tree.indexOfTopLevelItem(self.video_tree.currentItem())

        if not peer or index < 0 or index >= len(self.videos):
            self.status.setText(self.texts["net_pick_first"])
            return

        video = self.videos[index]

        self.fetch_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)

        self.fetcher = Fetcher(
            peer, video,
            self.service.device_name, self.service.device_id,
            self.save_dir, self,
        )
        self.fetcher.progress.connect(self._on_progress)
        self.fetcher.done.connect(self._on_done)
        self.fetcher.start()

    def _cancel(self):
        if self.fetcher:
            self.fetcher.cancel()

    def _on_progress(self, percent, message):
        self.progress.setValue(percent)
        self.status.setText(message)

    def _on_done(self, ok, message):
        self.fetch_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setValue(100 if ok else 0)
        self.status.setText(message)

    # --- 들어온 요청 ---

    def _on_asked(self, req_id, peer_name, filename, size):
        peer_id = ""

        for p in self.service.listed_peers():
            if p["name"] == peer_name:
                peer_id = p["id"]
                break

        dialog = ApprovalDialog(self, self.texts, peer_name, filename, size)
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

        self.service.desk.decide(req_id, dialog.decision, peer_id, peer_name)

        label = {
            "yes": self.texts["net_allowed"],
            "always": self.texts["net_allowed_always"],
            "no": self.texts["net_denied"],
        }[dialog.decision]
        self.status.setText(label.format(peer=peer_name, name=filename))

        if dialog.decision == "always":
            self._reload_peers()

    def _on_settled(self, req_id, message):
        self.status.setText(message)

    def _on_failed(self, reason):
        self.status.setText(self.texts["net_failed"].format(error=reason))

    # --- 신뢰 목록 ---

    def _open_trusted(self):
        rows = self.service.trust.listed()

        if not rows:
            QMessageBox.information(
                self, self.texts["net_trusted"], self.texts["net_trusted_empty"]
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.texts["net_trusted"])
        dialog.setMinimumWidth(380)

        layout = QVBoxLayout(dialog)

        note = QLabel(self.texts["net_trusted_hint"])
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

        listing = QListWidget()

        for dev_id, meta in rows:
            item = QListWidgetItem(meta.get("name", dev_id))
            item.setData(Qt.UserRole, dev_id)
            listing.addItem(item)

        layout.addWidget(listing)

        buttons = QDialogButtonBox()
        remove = buttons.addButton(
            self.texts["net_untrust"], QDialogButtonBox.ActionRole
        )
        close = buttons.addButton(
            self.texts["close"], QDialogButtonBox.RejectRole
        )

        def do_remove():
            item = listing.currentItem()

            if not item:
                return

            self.service.trust.untrust(item.data(Qt.UserRole))
            listing.takeItem(listing.row(item))
            self._reload_peers()

        remove.clicked.connect(do_remove)
        close.clicked.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()


class UnavailableTab(QWidget):
    """zeroconf 가 없을 때 대신 보여 주는 안내."""

    def __init__(self, parent, texts):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addStretch()

        label = QLabel(texts["net_no_zeroconf"])
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        layout.addStretch()
