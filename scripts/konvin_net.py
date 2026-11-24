#!/usr/bin/env python3
"""
Konvin 네트워크 라이브러리 — 같은 네트워크의 다른 Konvin 과 영상을 주고받는다.

konvin.py 가 이 모듈을 불러 "네트워크" 탭을 만든다.

동작 요약
    1. zeroconf 로 같은 네트워크의 Konvin 을 찾고, 나도 광고한다
    2. 각자 작은 HTTPS 서버를 띄운다. 인증서는 기기마다 스스로 만든 것이고,
       상대는 인증서의 지문(SHA-256)으로 서버를 확인한다
    3. 처음 만난 기기와는 페어링을 한다. 한쪽 화면에 뜬 6자리 코드를 다른 쪽에
       입력해야 하고, 맞으면 두 기기만 아는 비밀키가 만들어진다
    4. 페어링된 기기만 영상 목록을 볼 수 있다. 요청마다 비밀키로 서명한다
    5. 파일을 받으려면 상대에게 요청을 보내고, 상대가 허용해야 한다
    6. 허용되면 일회용 토큰이 나오고, 그걸로 파일을 받는다

승인 없이는 어떤 파일도 나가지 않는다. "이 컴퓨터는 항상 허용" 을 고르면
그 기기만 다음부터 묻지 않는다.

페어링 절차 (가운데에 끼어든 기기가 코드를 맞출 수 없게 하는 순서)
    요청하는 쪽 A, 받는 쪽 B.
    1. A 가 무작위 값 na 를 만들고, 그 해시(약속)를 먼저 보낸다
    2. B 가 무작위 값 nb 를 돌려준다
    3. A 가 na 를 공개한다. B 는 1번의 약속과 맞는지 확인한다
    4. 양쪽이 (A 지문, B 지문, na, nb) 로 6자리 코드를 계산한다
    5. A 화면의 코드를 B 에 입력한다. 맞으면 B 가 비밀키를 만들어 넘겨준다
    A 가 쓰는 "B 지문" 은 실제로 연결된 서버의 인증서에서 나온 값이라,
    누군가 가운데에서 다른 인증서를 내밀면 양쪽 코드가 달라진다.
"""

import datetime
import hashlib
import hmac
import http.client
import json
import os
import secrets
import shutil
import socket
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
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
PROTOCOL_VERSION = "5"

VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}

ASK_TIMEOUT = 60        # 확인 창을 몇 초 기다릴지
TOKEN_LIFETIME = 300    # 토큰이 몇 초 뒤 만료되는지
MAX_PENDING = 20        # 동시에 떠 있을 수 있는 승인 대기 요청 수
CHUNK = 256 * 1024

PAIR_TIMEOUT = 120      # 페어링 한 번이 몇 초 안에 끝나야 하는지
PAIR_COOLDOWN = 30      # 거부한 뒤 몇 초 동안 새 페어링 창을 띄우지 않을지
MAX_PAIR_SESSIONS = 8   # 동시에 붙들고 있을 페어링 시도 수

MAX_JSON_BODY = 64 * 1024               # 받는 요청 본문 상한
MAX_REPLY_BYTES = 2 * 1024 * 1024       # 상대의 JSON 응답 상한
MAX_LISTING_ITEMS = 5000                # 목록에서 받아들일 영상 수
MAX_FILE_SIZE = 4 * 1024 ** 3           # 받을 파일 하나의 상한 (FAT32 한계)
DISK_MARGIN = 64 * 1024 * 1024          # 받은 뒤에도 남겨 둘 디스크 여유
MAX_CONNECTIONS = 32                    # 동시에 처리할 연결 수
SOCKET_TIMEOUT = 30                     # 연결 하나가 멈춰 있을 수 있는 시간
HANDSHAKE_TIMEOUT = 5                   # TLS 악수를 끝내야 하는 시간
NAME_LIMIT = 64                         # 기기 이름 길이 상한


def zeroconf_available():
    """zeroconf 가 깔려 있는지. 없으면 네트워크 탭을 안내문으로 대체한다."""
    try:
        import zeroconf  # noqa: F401
        return True
    except ImportError:
        return False


def crypto_available():
    """cryptography 가 깔려 있는지. 인증서를 만드는 데 필요하다."""
    try:
        import cryptography  # noqa: F401
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


def is_hex(value, length):
    """정확히 length 글자의 소문자 16진수 문자열인지."""
    return (
        isinstance(value, str)
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def is_device_id(value):
    """기기 ID 로 받아들일 수 있는 모양인지. HTTP 머리말에 실리므로 좁게 본다."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= 64
        and all(c.isascii() and (c.isalnum() or c == "-") for c in value)
    )


def clean_name(value, fallback="(이름 없음)"):
    """바깥에서 온 이름을 화면에 보여도 되게 다듬는다."""
    if not isinstance(value, str):
        return fallback

    text = "".join(c for c in value if c.isprintable()).strip()

    return text[:NAME_LIMIT] or fallback


def write_private(path, data):
    """주인만 읽을 수 있는 파일로 쓴다 (비밀키가 들어가는 파일용)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")

    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    with os.fdopen(fd, "wb") as f:
        f.write(data)

    os.replace(tmp, path)


# ============================================
# 암호 쪽 살림
# ============================================

def commitment(nonce, fingerprint, dev_id):
    """페어링 1단계에서 먼저 보내는 약속. 나중에 nonce 를 공개해 증명한다."""
    text = f"konvin-pair-commit\n{nonce}\n{fingerprint}\n{dev_id}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pairing_code(fp_a, fp_b, nonce_a, nonce_b):
    """양쪽 화면에서 같아야 하는 6자리 코드."""
    text = f"konvin-pair-code\n{fp_a}\n{fp_b}\n{nonce_a}\n{nonce_b}"
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def sign(key, method, path, nonce, server_fp):
    """요청 하나에 붙이는 서명. 비밀키 자체는 네트워크로 나가지 않는다."""
    text = f"konvin-auth\n{method}\n{path}\n{nonce}\n{server_fp}"
    return hmac.new(
        bytes.fromhex(key), text.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class Identity:
    """이 기기의 인증서와 개인키. 처음 한 번 만들어 두고 계속 쓴다.

    인증서의 SHA-256 지문이 네트워크에서 이 기기를 가리키는 값이 된다.
    """

    def __init__(self, directory, dev_id):
        self.cert_path = Path(directory) / "net_cert.pem"
        self.key_path = Path(directory) / "net_key.pem"

        if not self._usable():
            self._create(dev_id)

        pem = self.cert_path.read_text(encoding="ascii")
        self.fingerprint = hashlib.sha256(
            ssl.PEM_cert_to_DER_cert(pem)
        ).hexdigest()

    def _usable(self):
        if not (self.cert_path.is_file() and self.key_path.is_file()):
            return False

        try:
            self.server_context()
        except (OSError, ssl.SSLError, ValueError):
            return False

        return True

    def _create(self, dev_id):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, f"konvin-{dev_id[:8]}"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)

        # 유효 기간은 형식일 뿐이다. 상대는 날짜가 아니라 지문으로 확인한다.
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365 * 20))
            .sign(key, hashes.SHA256())
        )

        write_private(self.key_path, key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        write_private(
            self.cert_path, cert.public_bytes(serialization.Encoding.PEM)
        )

    def server_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(str(self.cert_path), str(self.key_path))
        return context


def client_context():
    """상대 서버에 붙을 때 쓰는 설정.

    인증 기관을 쓰지 않으므로 기본 검증은 끄고, 연결 직후 인증서 지문을
    직접 비교한다 (PinnedConnection).
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class NetError(Exception):
    """상대와 이야기하다 생긴 문제. 메시지는 화면에 그대로 보여도 된다."""


class PinMismatch(OSError):
    """상대 서버의 인증서가 기대한 지문과 다르다."""


class PinnedConnection(http.client.HTTPSConnection):
    """인증서 지문이 맞는 서버에만 요청을 보내는 연결."""

    def __init__(self, host, port, fingerprint, timeout):
        super().__init__(host, port, timeout=timeout, context=client_context())
        self.fingerprint = fingerprint

    def connect(self):
        super().connect()

        der = self.sock.getpeercert(binary_form=True)
        seen = hashlib.sha256(der).hexdigest() if der else ""

        if not hmac.compare_digest(seen, self.fingerprint):
            self.close()
            raise PinMismatch("인증서 지문이 다릅니다")


class PeerClient:
    """상대 한 대와 이야기하는 창구.

    fingerprint 는 반드시 맞아야 하는 서버 인증서 지문이다. 페어링된 상대라면
    저장해 둔 지문을, 처음 만난 상대라면 광고에 실린 지문을 넣는다.
    key 가 있으면 요청마다 서명을 붙인다.
    """

    def __init__(self, address, port, fingerprint, my_id="", key=""):
        self.address = address
        self.port = port
        self.fingerprint = fingerprint
        self.my_id = my_id
        self.key = key

    def open(self, method, path, payload=None, timeout=10):
        """요청을 보내고 (연결, 응답) 을 돌려준다. 닫는 것은 부른 쪽 몫이다."""
        headers = {"Accept": "application/json", "Connection": "close"}
        data = None

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        if self.key:
            nonce = secrets.token_hex(16)
            headers["X-Konvin-Id"] = self.my_id
            headers["X-Konvin-Nonce"] = nonce
            headers["X-Konvin-Auth"] = sign(
                self.key, method, path, nonce, self.fingerprint
            )

        connection = PinnedConnection(
            self.address, self.port, self.fingerprint, timeout
        )

        try:
            connection.request(method, path, body=data, headers=headers)
            return connection, connection.getresponse()
        except PinMismatch:
            connection.close()
            raise NetError(
                "상대의 인증서가 기억해 둔 것과 다릅니다. 연결하지 않았습니다."
            )
        except (OSError, http.client.HTTPException) as e:
            connection.close()
            raise NetError(f"연결하지 못했습니다: {e}")

    def json(self, method, path, payload=None, timeout=10):
        """JSON 을 주고받는다. (상태 코드, 딕셔너리) 를 돌려준다."""
        connection, response = self.open(method, path, payload, timeout)

        try:
            raw = response.read(MAX_REPLY_BYTES + 1)
        except (OSError, http.client.HTTPException) as e:
            raise NetError(f"응답을 받지 못했습니다: {e}")
        finally:
            connection.close()

        if len(raw) > MAX_REPLY_BYTES:
            raise NetError("상대의 응답이 너무 큽니다.")

        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise NetError("상대의 응답을 읽지 못했습니다.")

        if not isinstance(data, dict):
            raise NetError("상대의 응답을 읽지 못했습니다.")

        return response.status, data


def clean_listing(payload):
    """상대가 준 영상 목록에서 믿고 쓸 수 있는 항목만 남긴다."""
    videos = payload.get("videos")

    if not isinstance(videos, list):
        return []

    cleaned = []

    for v in videos[:MAX_LISTING_ITEMS]:
        if not isinstance(v, dict):
            continue

        file_id = v.get("id")
        filename = v.get("filename")
        size = v.get("size")

        if not (isinstance(file_id, str) and 0 < len(file_id) <= 64):
            continue

        if not isinstance(filename, str):
            continue

        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            continue

        # 디렉터리 부분은 여기서 떼어 낸다. 받을 때 한 번 더 확인한다.
        name = os.path.basename(filename)
        name = "".join(c for c in name if c.isprintable())[:255]

        if not name or name in (".", ".."):
            continue

        cleaned.append({"id": file_id, "filename": name, "size": size})

    return cleaned


# ============================================
# 저장되는 것들
# ============================================

class JsonStore:
    """딕셔너리 하나를 JSON 파일로 들고 있는 저장소의 공통 부분."""

    private = False     # True 면 주인만 읽을 수 있게 쓴다

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            return {}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def _save(self):
        text = json.dumps(self.data, ensure_ascii=False, indent=2)

        try:
            if self.private:
                write_private(self.path, text.encode("utf-8"))
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(text, encoding="utf-8")
        except OSError:
            pass


class PairStore(JsonStore):
    """페어링된 기기. 기기마다 인증서 지문과 둘만 아는 비밀키를 기억한다."""

    private = True

    def get(self, dev_id):
        with self.lock:
            entry = self.data.get(dev_id)

        if not isinstance(entry, dict):
            return None

        if not (is_hex(entry.get("fp"), 64) and is_hex(entry.get("key"), 64)):
            return None

        return dict(entry)

    def is_paired(self, dev_id):
        return self.get(dev_id) is not None

    def add(self, dev_id, name, fingerprint, key):
        with self.lock:
            self.data[dev_id] = {
                "name": name,
                "fp": fingerprint,
                "key": key,
                "since": int(time.time()),
            }
            self._save()

    def remove(self, dev_id):
        with self.lock:
            gone = self.data.pop(dev_id, None)
            self._save()

        return gone

    def listed(self):
        with self.lock:
            ids = list(self.data)

        return [(i, e) for i in ids if (e := self.get(i))]


class TrustStore(JsonStore):
    """'항상 허용' 을 고른 기기를 기억한다.

    여기 적힌 ID 만으로는 아무것도 허용되지 않는다. 요청이 페어링 비밀키로
    서명돼 그 기기가 맞다고 확인된 뒤에만 이 목록을 본다.
    """

    def is_trusted(self, dev_id):
        with self.lock:
            return dev_id in self.data

    def trust(self, dev_id, name):
        with self.lock:
            self.data[dev_id] = {"name": name, "since": int(time.time())}
            self._save()

    def untrust(self, dev_id):
        with self.lock:
            gone = self.data.pop(dev_id, None)
            self._save()

        return gone


class AliasStore(JsonStore):
    """상대 컴퓨터에 내가 붙인 이름.

    이 이름은 내 컴퓨터에만 저장되고 상대에게 알려지지 않는다. 상대가 자기
    이름을 바꿔도 여기서 붙인 이름은 그대로 남는다.
    """

    def get(self, dev_id):
        with self.lock:
            name = self.data.get(dev_id, "")

        return name if isinstance(name, str) else ""

    def set(self, dev_id, name):
        name = (name or "").strip()

        with self.lock:
            if name:
                self.data[dev_id] = name
            else:
                self.data.pop(dev_id, None)

            self._save()

    def label(self, peer):
        """화면에 보일 이름. 내가 붙인 이름이 있으면 그걸 쓴다."""
        return self.get(peer.get("id", "")) or peer.get("name", "(이름 없음)")


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

    HTTP 스레드에서 호출되지만 화면에 묻는 일은 신호로 넘긴다. 여기까지 온
    요청은 모두 페어링 비밀키로 확인된 기기의 것이다.
    """

    asked = Signal(str, str, str, str, int)   # req_id, 상대 id, 상대 이름, 파일, 크기
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
                "owner": peer_id,
            }

        if self.trust.is_trusted(peer_id):
            self._approve(req_id, file_id, peer_id)
            self.settled.emit(req_id, f"{peer_name} → {filename} (자동 허용)")
            return req_id, "허용"

        # 승인 대기 요청이 너무 많으면 더 받지 않는다 (확인 창 폭주 방지)
        with self.lock:
            pending = sum(1 for e in self.requests.values()
                          if e["state"] == "대기")

        if pending > MAX_PENDING:
            with self.lock:
                self.requests[req_id]["state"] = "거부"
            return req_id, "거부"

        # 화면 쪽에서 받아 확인 창을 띄운다
        self.asked.emit(req_id, peer_id, peer_name, filename, size)

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
            owner = entry["owner"]

        if decision in ("yes", "always"):
            self._approve(req_id, file_id, owner)
        else:
            with self.lock:
                if req_id in self.requests:
                    self.requests[req_id]["state"] = "거부"

    def _approve(self, req_id, file_id, owner):
        token = secrets.token_urlsafe(24)

        with self.lock:
            self.tokens[token] = (file_id, time.time(), owner)

            if req_id in self.requests:
                self.requests[req_id]["state"] = "허용"
                self.requests[req_id]["token"] = token

    def status(self, req_id, owner):
        """요청한 기기 본인에게만 상태와 토큰을 알려 준다."""
        with self.lock:
            entry = self.requests.get(req_id)

            if not entry or entry["owner"] != owner:
                return {"state": "없음", "token": None}

            # 너무 오래 대기한 요청은 거부로 본다
            if entry["state"] == "대기" and time.time() - entry["at"] > ASK_TIMEOUT:
                entry["state"] = "거부"

            return {"state": entry["state"], "token": entry["token"]}

    def take_token(self, token, owner):
        """토큰을 한 번만 쓸 수 있게 꺼낸다. 발급받은 기기만 쓸 수 있다."""
        with self.lock:
            entry = self.tokens.get(token)

            if not entry or entry[2] != owner:
                return None

            del self.tokens[token]

        file_id, issued, _ = entry

        return None if time.time() - issued > TOKEN_LIFETIME else file_id

    def sweep(self):
        now = time.time()

        with self.lock:
            for t in [t for t, (_, at, _) in self.tokens.items()
                      if now - at > TOKEN_LIFETIME]:
                del self.tokens[t]

            for r in [r for r, e in self.requests.items()
                      if now - e["at"] > TOKEN_LIFETIME * 2]:
                del self.requests[r]


class PairDesk(QObject):
    """들어온 페어링 시도를 붙들고, 사람이 코드를 입력할 때까지 기다린다.

    한 번에 하나의 시도만 화면에 올린다. 코드를 맞출 기회는 시도마다 한 번이다.
    """

    asked = Signal(str, str)    # pair_id, 상대 이름

    def __init__(self, pairs, trust, parent=None):
        super().__init__(parent)
        self.pairs = pairs
        self.trust = trust
        self.sessions = {}
        self.active = None
        self.quiet_until = 0.0
        self.lock = threading.Lock()

        # NetService.start() 가 채운다
        self.my_id = ""
        self.my_name = ""
        self.my_fp = ""

    def _prune(self):
        """lock 을 쥔 채로 부른다."""
        now = time.time()

        for pair_id in [p for p, s in self.sessions.items()
                        if now - s["at"] > PAIR_TIMEOUT]:
            del self.sessions[pair_id]

            if self.active == pair_id:
                self.active = None

    def start(self, dev_id, name, fingerprint, commit):
        """1단계: 상대의 약속을 받아 두고 내 무작위 값을 돌려준다."""
        with self.lock:
            self._prune()

            if len(self.sessions) >= MAX_PAIR_SESSIONS:
                return None

            pair_id = secrets.token_urlsafe(12)
            nonce = secrets.token_hex(32)

            self.sessions[pair_id] = {
                "id": dev_id,
                "name": name,
                "fp": fingerprint,
                "commit": commit,
                "nonce": nonce,
                "at": time.time(),
                "state": "시작",
                "code": None,
                "key": None,
            }

        return pair_id, nonce

    def reveal(self, pair_id, nonce_a):
        """2단계: 상대가 공개한 값이 약속과 맞으면 화면에 코드를 묻는다."""
        with self.lock:
            self._prune()
            session = self.sessions.get(pair_id)

            if not session or session["state"] != "시작":
                return "없음"

            expected = commitment(nonce_a, session["fp"], session["id"])

            if not hmac.compare_digest(expected, session["commit"]):
                session["state"] = "거부"
                return "거부"

            # 이미 다른 시도가 화면에 떠 있거나, 방금 거부한 직후면 받지 않는다
            if self.active is not None or time.time() < self.quiet_until:
                session["state"] = "거부"
                return "거부"

            session["code"] = pairing_code(
                session["fp"], self.my_fp, nonce_a, session["nonce"]
            )
            session["state"] = "대기"
            self.active = pair_id
            name = session["name"]

        self.asked.emit(pair_id, name)

        return "대기"

    def decide(self, pair_id, typed):
        """화면에서 입력한 코드를 받는다. 'ok' / 'mismatch' / 'gone' 을 돌려준다."""
        typed = "".join(c for c in (typed or "") if c.isdigit())

        with self.lock:
            if self.active == pair_id:
                self.active = None

            self._prune()
            session = self.sessions.get(pair_id)

            if not session or session["state"] != "대기":
                return "gone"

            if not typed:
                session["state"] = "거부"
                self.quiet_until = time.time() + PAIR_COOLDOWN
                return "denied"

            if not hmac.compare_digest(typed, session["code"]):
                session["state"] = "거부"
                self.quiet_until = time.time() + PAIR_COOLDOWN
                return "mismatch"

            key = secrets.token_hex(32)
            session["key"] = key
            session["state"] = "허용"
            dev_id, name, fingerprint = (
                session["id"], session["name"], session["fp"]
            )

        # 같은 ID 가 다른 인증서로 다시 페어링하면 예전의 '항상 허용' 은 지운다
        previous = self.pairs.get(dev_id)

        if previous and previous["fp"] != fingerprint:
            self.trust.untrust(dev_id)

        self.pairs.add(dev_id, name, fingerprint, key)

        return "ok"

    def status(self, pair_id):
        """상대가 결과를 물어볼 때. 비밀키는 한 번만 내준다."""
        with self.lock:
            self._prune()
            session = self.sessions.get(pair_id)

            if not session:
                return {"state": "없음"}

            if session["state"] != "허용":
                state = "대기" if session["state"] == "시작" else session["state"]
                return {"state": state}

            key = session["key"]
            del self.sessions[pair_id]

        return {
            "state": "허용",
            "key": key,
            "id": self.my_id,
            "name": self.my_name,
        }


# ============================================
# HTTPS 서버
# ============================================

class Handler(BaseHTTPRequestHandler):

    library = None
    desk = None
    pair_desk = None
    pairs = None
    my_name = ""
    my_id = ""
    my_fp = ""
    notify = None       # 로그를 남기는 함수 (클래스 속성)

    protocol_version = "HTTP/1.1"
    timeout = SOCKET_TIMEOUT

    def setup(self):
        # TLS 악수는 연결마다 따로 도는 이 스레드에서 한다. 접속을 받는
        # 스레드에서 하면 악수를 끄는 연결 하나가 서버 전체를 세운다.
        self.request.settimeout(HANDSHAKE_TIMEOUT)
        self.request.do_handshake()
        super().setup()

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
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _peer(self):
        """서명이 맞는 페어링된 기기면 (id, 정보) 를, 아니면 None 을 돌려준다."""
        dev_id = self.headers.get("X-Konvin-Id", "")
        nonce = self.headers.get("X-Konvin-Nonce", "")
        mac = self.headers.get("X-Konvin-Auth", "")

        if not (is_device_id(dev_id) and is_hex(nonce, 32) and is_hex(mac, 64)):
            return None

        entry = self.pairs.get(dev_id)

        if not entry:
            return None

        expected = sign(entry["key"], self.command, self.path, nonce, self.my_fp)

        if not hmac.compare_digest(expected, mac):
            return None

        return dev_id, entry

    def _require_peer(self):
        peer = self._peer()

        if not peer:
            self._json({"error": "페어링이 필요합니다"}, status=401)

        return peer

    def _body(self):
        """요청 본문을 딕셔너리로 읽는다. 못 읽으면 400 을 보내고 None."""
        try:
            length = int(self.headers.get("Content-Length", 0))

            if length < 0 or length > MAX_JSON_BODY:
                self._json({"error": "요청이 너무 큽니다"}, status=400)
                return None

            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, OSError):
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return None

        if not isinstance(body, dict):
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return None

        return body

    # --- GET ---

    def do_GET(self):
        if self.path.startswith("/pair/") and self.path.endswith("/status"):
            pair_id = self.path[len("/pair/"):-len("/status")]
            self._json(self.pair_desk.status(pair_id))
            return

        # 여기부터는 페어링된 기기만
        peer = self._require_peer()

        if not peer:
            return

        dev_id, _ = peer

        if self.path == "/videos":
            self._json({
                "device": {"name": self.my_name, "id": self.my_id},
                "videos": self.library.scan(),
            })
            return

        if self.path.startswith("/request/") and self.path.endswith("/status"):
            req_id = self.path[len("/request/"):-len("/status")]
            self._json(self.desk.status(req_id, dev_id))
            return

        if self.path.startswith("/download/"):
            self._download(self.path[len("/download/"):], dev_id)
            return

        self._json({"error": "없는 경로입니다"}, status=404)

    def _download(self, token, dev_id):
        file_id = self.desk.take_token(token, dev_id)

        if not file_id:
            self._json({"error": "토큰이 없거나 만료됐습니다"}, status=403)
            return

        info = self.library.info_for(file_id)

        if not info:
            self._json({"error": "파일을 찾을 수 없습니다"}, status=404)
            return

        path, size = info["path"], info["size"]

        self._say(f"보내는 중: {path.name} ({human_size(size)})")

        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            with path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile, length=CHUNK)
        except OSError:
            self._say(f"전송이 끊겼습니다: {path.name}")
            return

        self._say(f"보냈습니다: {path.name}")

    # --- POST ---

    def do_POST(self):
        if self.path == "/pair/start":
            self._pair_start()
            return

        if self.path == "/pair/reveal":
            self._pair_reveal()
            return

        if self.path != "/request":
            self._json({"error": "없는 경로입니다"}, status=404)
            return

        peer = self._require_peer()

        if not peer:
            return

        dev_id, entry = peer
        body = self._body()

        if body is None:
            return

        file_id = body.get("file_id", "")

        if not isinstance(file_id, str):
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return

        self.library.scan()
        info = self.library.info_for(file_id)

        if not info:
            self._json({"error": "그런 파일이 없습니다"}, status=404)
            return

        # 이름과 ID 는 요청 본문이 아니라 페어링 기록에서 가져온다
        req_id, state = self.desk.submit(
            clean_name(entry.get("name")),
            dev_id,
            file_id,
            info["path"].name,
            info["size"],
        )
        self._json({"request_id": req_id, "state": state})

    def _pair_start(self):
        body = self._body()

        if body is None:
            return

        dev_id = body.get("id")
        fingerprint = body.get("fp")
        commit = body.get("commit")

        if not (is_device_id(dev_id) and is_hex(fingerprint, 64)
                and is_hex(commit, 64)) or dev_id == self.my_id:
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return

        started = self.pair_desk.start(
            dev_id, clean_name(body.get("name")), fingerprint, commit
        )

        if not started:
            self._json({"error": "지금은 페어링을 받을 수 없습니다"}, status=429)
            return

        pair_id, nonce = started
        self._json({"pair_id": pair_id, "nonce": nonce})

    def _pair_reveal(self):
        body = self._body()

        if body is None:
            return

        pair_id = body.get("pair_id")
        nonce = body.get("nonce")

        if not (isinstance(pair_id, str) and is_hex(nonce, 64)):
            self._json({"error": "요청을 읽지 못했습니다"}, status=400)
            return

        self._json({"state": self.pair_desk.reveal(pair_id, nonce)})


class TLSServer(ThreadingHTTPServer):
    """연결마다 TLS 를 씌우고, 동시에 처리할 연결 수를 제한하는 서버."""

    daemon_threads = True

    def __init__(self, address, handler, context):
        super().__init__(address, handler)
        self.context = context
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def get_request(self):
        sock, address = self.socket.accept()

        # 악수는 여기서 하지 않는다 (Handler.setup 참고)
        wrapped = self.context.wrap_socket(
            sock, server_side=True, do_handshake_on_connect=False
        )

        return wrapped, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return

        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # 악수 실패나 끊긴 연결은 흔하다. 터미널을 어지럽히지 않는다.
        pass


# ============================================
# 서비스 (발견 + 서버)
# ============================================

class NetService(QObject):
    """앱이 켜져 있는 동안 계속 도는 네트워크 쪽 살림."""

    peers_changed = Signal()
    log = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, device_name, device_id, trust_path,
                 alias_path, parent=None):
        super().__init__(parent)

        # 인증서와 페어링 기록은 신뢰 목록과 같은 폴더에 둔다
        self.base = Path(trust_path).parent

        self.library = Library(folder)
        self.trust = TrustStore(trust_path)
        self.aliases = AliasStore(alias_path)
        self.pairs = PairStore(self.base / "paired_devices.json")
        self.desk = RequestDesk(self.trust, self)
        self.pair_desk = PairDesk(self.pairs, self.trust, self)

        self.device_name = clean_name(device_name, "Konvin")
        self.device_id = device_id
        self.identity = None

        self.peers = {}
        self.workers = []
        self.lock = threading.Lock()

        self.zc = None
        self.info = None
        self.browser = None
        self.server = None
        self.port = None
        self.running = False
        self.last_error = ""
        self.bind_address = ""      # 비워 두면 랜 주소를 알아서 고른다

    @property
    def fingerprint(self):
        return self.identity.fingerprint if self.identity else ""

    def _fail(self, reason):
        self.last_error = reason
        self.failed.emit(reason)

    # --- 시작 / 끝 ---

    def start(self):
        if self.running:
            return True

        try:
            from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
        except ImportError:
            self._fail("zeroconf")
            return False

        try:
            self.identity = Identity(self.base, self.device_id)
        except Exception as e:
            self._fail(f"인증서를 준비하지 못했습니다: {e}")
            return False

        self.pair_desk.my_id = self.device_id
        self.pair_desk.my_name = self.device_name
        self.pair_desk.my_fp = self.identity.fingerprint

        self.library.scan()

        # 이 서비스의 살림을 물려받은 처리기. 전역 Handler 는 건드리지 않는다.
        handler = type("BoundHandler", (Handler,), {
            "library": self.library,
            "desk": self.desk,
            "pair_desk": self.pair_desk,
            "pairs": self.pairs,
            "my_name": self.device_name,
            "my_id": self.device_id,
            "my_fp": self.identity.fingerprint,
            "notify": self.log.emit,
        })

        ip = self.bind_address or local_ip()

        # 랜 주소 하나에만 연다. VPN 이나 가상 머신용 인터페이스에는 열지 않는다.
        try:
            self.server = TLSServer(
                (ip, 0), handler, self.identity.server_context()
            )
        except (OSError, ssl.SSLError) as e:
            self._fail(str(e))
            return False

        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

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
                    "fp": self.identity.fingerprint,
                    "ver": PROTOCOL_VERSION,
                },
            )
            self.zc.register_service(self.info)
            self.browser = ServiceBrowser(self.zc, SERVICE_TYPE, self)
        except Exception as e:
            self._fail(str(e))
            self.stop()
            return False

        self.running = True
        self.log.emit(f"네트워크 시작 — {ip}:{self.port}")

        return True

    def track(self, worker):
        """돌고 있는 작업 스레드를 기억해 둔다. 끌 때 기다려 주기 위해서다."""
        self.workers = [w for w in self.workers if w.isRunning()]
        self.workers.append(worker)

    def stop(self):
        self.running = False

        # 스레드가 도는 채로 창이 닫히면 Qt 가 프로그램을 강제로 끝낸다
        for worker in self.workers:
            if worker.isRunning():
                worker.cancel()
                worker.wait(SOCKET_TIMEOUT * 1000 + 2000)

        self.workers = []

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

        try:
            props = {
                k.decode("utf-8"): v.decode("utf-8")
                for k, v in info.properties.items()
                if k and v
            }
        except UnicodeDecodeError:
            return None

        addresses = [socket.inet_ntoa(a) for a in info.addresses]

        if not addresses:
            return None

        # 지문을 광고하지 않는 예전 버전은 목록에 올리지 않는다
        if not (is_device_id(props.get("id")) and is_hex(props.get("fp"), 64)):
            return None

        return {
            "name": clean_name(props.get("name")),
            "id": props["id"],
            "fp": props["fp"],
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
        self.add_service(zc, type_, name)

    def listed_peers(self):
        with self.lock:
            return list(self.peers.values())

    # --- 상대에게 붙는 창구 ---

    def client_for(self, peer):
        """페어링된 상대에게 서명을 붙여 말하는 창구. 페어링 전이면 None.

        인증서 지문은 광고에 실린 값이 아니라 페어링 때 저장한 값을 쓴다.
        """
        entry = self.pairs.get(peer.get("id", ""))

        if not entry:
            return None

        return PeerClient(
            peer["address"], peer["port"], entry["fp"],
            self.device_id, entry["key"],
        )


# ============================================
# 작업 스레드
# ============================================

class VideoLoader(QThread):
    """상대의 영상 목록을 불러온다. 느린 상대가 화면을 세우지 않게 따로 돈다."""

    loaded = Signal(int, list)      # 순번, 영상 목록
    failed = Signal(int, str, str)  # 순번, 종류("pair" / "error"), 설명

    def __init__(self, seq, client, parent=None):
        super().__init__(parent)
        self.seq = seq
        self.client = client

    def cancel(self):
        pass

    def run(self):
        try:
            status, payload = self.client.json("GET", "/videos", timeout=8)
        except NetError as e:
            self.failed.emit(self.seq, "error", str(e))
            return

        if status == 401:
            self.failed.emit(self.seq, "pair", "")
            return

        if status != 200:
            self.failed.emit(self.seq, "error", f"상대가 거절했습니다 ({status})")
            return

        self.loaded.emit(self.seq, clean_listing(payload))


class Pairer(QThread):
    """처음 만난 기기와 페어링한다 (요청하는 쪽)."""

    code_ready = Signal(str)        # 상대 화면에 입력할 코드
    done = Signal(bool, str)        # 성공 여부, 메시지

    def __init__(self, peer, service, parent=None):
        super().__init__(parent)
        self.peer = peer
        self.service = service
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            self._pair()
        except NetError as e:
            self.done.emit(False, str(e))

    def _pair(self):
        peer = self.peer
        my_id = self.service.device_id
        my_fp = self.service.fingerprint

        # 광고에 실린 지문의 서버에만 붙는다. 누가 광고를 바꿔치기했다면
        # 양쪽 코드가 달라져 여기서 드러난다.
        client = PeerClient(peer["address"], peer["port"], peer["fp"])

        nonce_a = secrets.token_hex(32)

        status, reply = client.json("POST", "/pair/start", {
            "id": my_id,
            "name": self.service.device_name,
            "fp": my_fp,
            "commit": commitment(nonce_a, my_fp, my_id),
        })

        if status != 200:
            self.done.emit(False, "상대가 지금은 페어링을 받을 수 없습니다.")
            return

        pair_id = reply.get("pair_id")
        nonce_b = reply.get("nonce")

        if not (isinstance(pair_id, str) and is_hex(nonce_b, 64)):
            self.done.emit(False, "상대의 응답을 읽지 못했습니다.")
            return

        self.code_ready.emit(pairing_code(my_fp, peer["fp"], nonce_a, nonce_b))

        status, reply = client.json("POST", "/pair/reveal", {
            "pair_id": pair_id,
            "nonce": nonce_a,
        })

        if status != 200 or reply.get("state") != "대기":
            self.done.emit(
                False, "상대가 다른 페어링을 처리하는 중이거나 거부했습니다."
            )
            return

        waited = 0

        while waited < PAIR_TIMEOUT + 5:
            if self._stop:
                self.done.emit(False, "취소했습니다.")
                return

            status, reply = client.json(
                "GET", f"/pair/{pair_id}/status", timeout=5
            )
            state = reply.get("state")

            if state == "허용":
                break

            if state != "대기":
                self.done.emit(
                    False, "상대가 거부했거나 코드가 맞지 않았습니다."
                )
                return

            time.sleep(1)
            waited += 1
        else:
            self.done.emit(False, "응답이 없어 그만뒀습니다.")
            return

        key = reply.get("key")

        if not is_hex(key, 64) or reply.get("id") != peer["id"]:
            self.done.emit(False, "상대의 응답을 읽지 못했습니다.")
            return

        previous = self.service.pairs.get(peer["id"])

        if previous and previous["fp"] != peer["fp"]:
            self.service.trust.untrust(peer["id"])

        self.service.pairs.add(
            peer["id"], clean_name(reply.get("name"), peer["name"]),
            peer["fp"], key,
        )
        self.done.emit(True, "")


class Fetcher(QThread):
    """요청 → 승인 대기 → 받기. 화면이 멈추지 않게 따로 돈다."""

    progress = Signal(int, str)     # 퍼센트, 설명
    done = Signal(bool, str)        # 성공 여부, 메시지

    def __init__(self, client, video, save_dir, parent=None):
        super().__init__(parent)
        self.client = client
        self.video = video
        self.save_dir = Path(save_dir)
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            self._fetch()
        except NetError as e:
            self.done.emit(False, str(e))

    def _fetch(self):
        video = self.video

        # 상대가 준 파일 이름을 그대로 경로에 쓰지 않는다. 디렉터리 부분을
        # 떼어내고 저장 폴더를 벗어나지 않는지 확인한다 (경로 탈출 방지).
        safe_name = os.path.basename(str(video.get("filename", "")))

        if not safe_name or safe_name in (".", ".."):
            self.done.emit(False, "받을 파일 이름이 올바르지 않습니다.")
            return

        target = (self.save_dir / safe_name).resolve()

        if self.save_dir.resolve() not in target.parents:
            self.done.emit(False, "저장 폴더를 벗어나는 경로입니다.")
            return

        if target.exists():
            self.done.emit(False, f"이미 같은 이름의 파일이 있습니다: {target.name}")
            return

        # 크기는 목록에서 본 값을 기준으로 삼고, 그보다 많이 오면 끊는다
        expected = video.get("size")

        if (isinstance(expected, bool) or not isinstance(expected, int)
                or expected <= 0):
            self.done.emit(False, "파일 크기를 알 수 없어 받지 않았습니다.")
            return

        if expected > MAX_FILE_SIZE:
            self.done.emit(
                False,
                f"파일이 너무 큽니다 ({human_size(expected)}, "
                f"상한 {human_size(MAX_FILE_SIZE)}).",
            )
            return

        self.save_dir.mkdir(parents=True, exist_ok=True)

        try:
            free = shutil.disk_usage(self.save_dir).free
        except OSError:
            free = None

        if free is not None and free < expected + DISK_MARGIN:
            self.done.emit(False, "디스크 공간이 부족합니다.")
            return

        # 1) 요청
        status, reply = self.client.json(
            "POST", "/request", {"file_id": video["id"]}
        )

        if status == 401:
            self.done.emit(
                False, "상대가 페어링을 해제했습니다. 다시 페어링하세요."
            )
            return

        if status != 200:
            self.done.emit(False, f"요청이 거절됐습니다 ({status})")
            return

        req_id = reply.get("request_id")

        if not isinstance(req_id, str):
            self.done.emit(False, "상대의 응답을 읽지 못했습니다.")
            return

        # 2) 승인 기다리기
        self.progress.emit(0, "상대의 승인을 기다리는 중...")
        token = None
        waited = 0

        while waited < ASK_TIMEOUT + 10:
            if self._stop:
                self.done.emit(False, "취소했습니다.")
                return

            _, reply = self.client.json(
                "GET", f"/request/{req_id}/status", timeout=5
            )

            if reply.get("state") == "허용":
                token = reply.get("token")
                break

            if reply.get("state") != "대기":
                self.done.emit(False, "상대가 거부했습니다.")
                return

            time.sleep(1)
            waited += 1

        if not isinstance(token, str) or not token:
            self.done.emit(False, "응답이 없어 그만뒀습니다.")
            return

        # 3) 받기
        self.progress.emit(0, "받는 중...")
        tmp = target.with_name(target.name + ".part")

        connection, response = self.client.open(
            "GET", f"/download/{token}", timeout=SOCKET_TIMEOUT
        )

        try:
            if response.status != 200:
                self.done.emit(False, f"받지 못했습니다 ({response.status})")
                return

            if response.getheader("Content-Length") != str(expected):
                self.done.emit(False, "상대가 알려 준 크기와 달라 받지 않았습니다.")
                return

            message = self._receive(response, tmp, expected)
        finally:
            connection.close()

        if message:
            tmp.unlink(missing_ok=True)
            self.done.emit(False, message)
            return

        try:
            tmp.replace(target)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            self.done.emit(False, f"저장하지 못했습니다: {e}")
            return

        self.done.emit(True, f"다 받았습니다: {target.name}")

    def _receive(self, response, tmp, expected):
        """본문을 tmp 에 받는다. 문제가 있으면 메시지를, 없으면 None 을 돌려준다."""
        got = 0

        try:
            with tmp.open("wb") as f:
                while got < expected:
                    if self._stop:
                        return "취소했습니다."

                    chunk = response.read(min(CHUNK, expected - got))

                    if not chunk:
                        break

                    f.write(chunk)
                    got += len(chunk)

                    self.progress.emit(
                        int(got / expected * 100),
                        f"받는 중... {human_size(got)} / {human_size(expected)}",
                    )
        except (OSError, http.client.HTTPException) as e:
            return f"받는 중 끊겼습니다: {e}"

        if got != expected:
            return f"크기가 다릅니다 (받은 {got}, 예상 {expected})"

        return None


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
        head.setTextFormat(Qt.PlainText)
        head.setWordWrap(True)
        layout.addWidget(head)

        file_label = QLabel(f"{filename}  ({human_size(size)})")
        file_label.setTextFormat(Qt.PlainText)
        file_label.setStyleSheet("font-weight: bold;")
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


class PairCodeDialog(QDialog):
    """페어링을 요청한 쪽에 뜨는 창. 상대 화면에 입력할 코드를 보여 준다."""

    def __init__(self, parent, texts, peer_name):
        super().__init__(parent)

        self.setWindowTitle(texts["net_pair_title"])
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        head = QLabel(texts["net_pair_show_body"].format(peer=peer_name))
        head.setTextFormat(Qt.PlainText)
        head.setWordWrap(True)
        layout.addWidget(head)

        self.code_label = QLabel("······")
        self.code_label.setTextFormat(Qt.PlainText)
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet(
            "font-size: 32px; font-weight: bold; letter-spacing: 6px;"
        )
        layout.addWidget(self.code_label)

        self.wait_label = QLabel(texts["net_pair_waiting"])
        self.wait_label.setWordWrap(True)
        self.wait_label.setStyleSheet("color: gray;")
        layout.addWidget(self.wait_label)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(texts["net_cancel"], QDialogButtonBox.RejectRole)
        cancel.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def show_code(self, code):
        self.code_label.setText(f"{code[:3]} {code[3:]}")


class PairApproveDialog(QDialog):
    """페어링 요청을 받은 쪽에 뜨는 창. 상대 화면의 코드를 입력받는다."""

    def __init__(self, parent, texts, peer_name):
        super().__init__(parent)

        self.typed = ""

        self.setWindowTitle(texts["net_pair_title"])
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        head = QLabel(texts["net_pair_ask_body"].format(peer=peer_name))
        head.setTextFormat(Qt.PlainText)
        head.setWordWrap(True)
        layout.addWidget(head)

        self.code_edit = QLineEdit()
        self.code_edit.setMaxLength(12)
        self.code_edit.setPlaceholderText("000 000")
        self.code_edit.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.code_edit)

        warning = QLabel(texts["net_pair_ask_warning"])
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b36b00;")
        layout.addWidget(warning)

        buttons = QDialogButtonBox()
        deny = buttons.addButton(texts["net_ask_deny"], QDialogButtonBox.RejectRole)
        allow = buttons.addButton(texts["net_pair"], QDialogButtonBox.AcceptRole)
        allow.setDefault(True)

        deny.clicked.connect(self.reject)
        allow.clicked.connect(self._allow)
        layout.addWidget(buttons)

    def _allow(self):
        self.typed = self.code_edit.text()
        self.accept()


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
        self.pairer = None
        self.load_seq = 0

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

        self.pair_button = QPushButton(texts["net_pair"])
        self.pair_button.clicked.connect(self._pair)
        left.addWidget(self.pair_button)

        self.rename_button = QPushButton(texts["net_rename"])
        self.rename_button.clicked.connect(self._rename_peer)
        left.addWidget(self.rename_button)

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
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        # --- 신호 연결 ---
        self.service.peers_changed.connect(self._reload_peers)
        self.service.desk.asked.connect(self._on_asked)
        self.service.desk.settled.connect(self._on_settled)
        self.service.pair_desk.asked.connect(self._on_pair_asked)
        self.service.log.connect(self.status.setText)
        self.service.failed.connect(self._on_failed)

        # 오래된 요청·토큰을 주기적으로 치운다 (메모리 증가·요청 누적 방지)
        self._sweep_timer = QTimer(self)
        self._sweep_timer.timeout.connect(self.service.desk.sweep)
        self._sweep_timer.start(30000)

        self._reload_peers()

        # 이 탭이 만들어지기 전에 시작이 실패했으면 그 이유를 보여 준다
        if not self.service.running and self.service.last_error:
            self._on_failed(self.service.last_error)

    # --- 목록 ---

    def _reload_peers(self):
        before = self._current_peer()
        chosen = before["id"] if before else None
        peers = self.service.listed_peers()

        # 다시 그리는 동안에는 선택 신호를 막는다. 기기가 나타나고 사라질
        # 때마다 영상 목록을 새로 불러오지 않기 위해서다.
        self.peer_list.blockSignals(True)
        self.peer_list.clear()

        for p in peers:
            marks = []

            if self.service.aliases.get(p["id"]):
                # 내가 붙인 이름을 쓰는 중이면 상대가 광고하는 이름도 곁들인다
                marks.append(p["name"])

            if self.service.pairs.is_paired(p["id"]):
                if self.service.trust.is_trusted(p["id"]):
                    marks.append(self.texts["net_trusted_mark"])
                else:
                    marks.append(self.texts["net_paired_mark"])

            suffix = f"  ({' · '.join(marks)})" if marks else ""
            item = QListWidgetItem(f"{self.service.aliases.label(p)}{suffix}")
            item.setData(Qt.UserRole, p)
            self.peer_list.addItem(item)

        for row, p in enumerate(peers):
            if p["id"] == chosen:
                self.peer_list.setCurrentRow(row)
                break

        self.peer_list.blockSignals(False)

        # 보고 있던 기기가 사라졌으면 그 기기의 영상 목록도 치운다
        if chosen and not self._current_peer():
            self._clear_videos()

    def _clear_videos(self):
        self.load_seq += 1      # 돌고 있는 불러오기의 결과는 버린다
        self.video_tree.clear()
        self.videos = []

    def _rename_peer(self):
        """상대에게 내 컴퓨터에서만 쓸 이름을 붙인다.

        상대에게는 알리지 않고, 상대가 자기 이름을 바꿔도 이 이름은 남는다.
        """
        peer = self._current_peer()

        if not peer:
            self.status.setText(self.texts["net_pick_peer"])
            return

        current = self.service.aliases.get(peer["id"])

        name, ok = QInputDialog.getText(
            self,
            self.texts["net_rename"],
            self.texts["net_rename_body"].format(peer=peer["name"]),
            text=current or peer["name"],
        )

        if not ok:
            return

        self.service.aliases.set(peer["id"], name)
        self._reload_peers()

        if name.strip():
            self.status.setText(
                self.texts["net_renamed"].format(name=name.strip())
            )
        else:
            self.status.setText(self.texts["net_rename_cleared"])

    def _current_peer(self):
        item = self.peer_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _peer_selected(self, row):
        if row >= 0:
            self._load_videos()

    def _load_videos(self):
        peer = self._current_peer()

        self._clear_videos()

        if not peer:
            return

        client = self.service.client_for(peer)

        if not client:
            self.status.setText(self.texts["net_need_pair"])
            return

        self.status.setText(self.texts["net_loading"])

        loader = VideoLoader(self.load_seq, client, self)
        loader.loaded.connect(self._on_loaded)
        loader.failed.connect(self._on_load_failed)
        loader.finished.connect(loader.deleteLater)
        self.service.track(loader)
        loader.start()

    def _on_loaded(self, seq, videos):
        peer = self._current_peer()

        if seq != self.load_seq or not peer:
            return

        self.videos = videos
        self.video_tree.clear()

        for v in videos:
            item = QTreeWidgetItem([v["filename"], human_size(v["size"])])
            self.video_tree.addTopLevelItem(item)

        self.status.setText(
            self.texts["net_loaded"].format(
                peer=self.service.aliases.label(peer),
                count=len(videos),
            )
        )

    def _on_load_failed(self, seq, kind, detail):
        if seq != self.load_seq:
            return

        if kind == "pair":
            # 지문이 확인된 상대가 "모르는 기기" 라고 답했다. 상대가 페어링을
            # 해제한 것이니 이쪽 기록도 지워 다시 페어링할 수 있게 한다.
            peer = self._current_peer()

            if peer:
                self.service.trust.untrust(peer["id"])
                self.service.pairs.remove(peer["id"])
                self._reload_peers()

            self.status.setText(self.texts["net_pair_lost"])
        else:
            self.status.setText(
                self.texts["net_connect_failed"].format(error=detail)
            )

    # --- 페어링 ---

    def _pair(self):
        if self.pairer and self.pairer.isRunning():
            return

        peer = self._current_peer()

        if not peer:
            self.status.setText(self.texts["net_pick_peer"])
            return

        if self.service.pairs.is_paired(peer["id"]):
            self.status.setText(self.texts["net_already_paired"])
            return

        label = self.service.aliases.label(peer)
        dialog = PairCodeDialog(self, self.texts, label)
        result = {}

        def finished(ok, message):
            result["ok"] = ok
            result["message"] = message
            dialog.accept()

        self.pairer = Pairer(peer, self.service, self)
        self.pairer.code_ready.connect(dialog.show_code)
        self.pairer.done.connect(finished)
        self.service.track(self.pairer)
        self.pairer.start()

        if dialog.exec() != QDialog.Accepted:
            self.pairer.cancel()

        if result.get("ok"):
            self.status.setText(self.texts["net_pair_done"].format(peer=label))
            self._reload_peers()
            self._load_videos()
        elif "message" in result:
            self.status.setText(result["message"])

    def _on_pair_asked(self, pair_id, peer_name):
        dialog = PairApproveDialog(self, self.texts, peer_name)
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

        outcome = self.service.pair_desk.decide(pair_id, dialog.typed)

        if outcome == "ok":
            self.status.setText(
                self.texts["net_pair_done"].format(peer=peer_name)
            )
            self._reload_peers()
        elif outcome == "mismatch":
            self.status.setText(self.texts["net_pair_mismatch"])
        else:
            self.status.setText(self.texts["net_pair_denied"])

    # --- 받기 ---

    def _fetch(self):
        if self.fetcher and self.fetcher.isRunning():
            return

        peer = self._current_peer()
        index = self.video_tree.indexOfTopLevelItem(self.video_tree.currentItem())

        if not peer or index < 0 or index >= len(self.videos):
            self.status.setText(self.texts["net_pick_first"])
            return

        client = self.service.client_for(peer)

        if not client:
            self.status.setText(self.texts["net_need_pair"])
            return

        video = self.videos[index]

        self.fetch_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)

        self.fetcher = Fetcher(client, video, self.save_dir, self)
        self.fetcher.progress.connect(self._on_progress)
        self.fetcher.done.connect(self._on_done)
        self.service.track(self.fetcher)
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

    def _on_asked(self, req_id, peer_id, peer_name, filename, size):
        # 내가 붙인 이름이 있으면 그걸로 보여 준다
        shown = self.service.aliases.get(peer_id) or peer_name

        dialog = ApprovalDialog(self, self.texts, shown, filename, size)
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

        self.service.desk.decide(req_id, dialog.decision, peer_id, peer_name)

        label = {
            "yes": self.texts["net_allowed"],
            "always": self.texts["net_allowed_always"],
            "no": self.texts["net_denied"],
        }[dialog.decision]
        self.status.setText(label.format(peer=shown, name=filename))

        if dialog.decision == "always":
            self._reload_peers()

    def _on_settled(self, req_id, message):
        self.status.setText(message)

    def _on_failed(self, reason):
        self.status.setText(self.texts["net_failed"].format(error=reason))

    # --- 페어링된 기기 목록 ---

    def _open_trusted(self):
        rows = self.service.pairs.listed()

        if not rows:
            QMessageBox.information(
                self, self.texts["net_trusted"], self.texts["net_paired_empty"]
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

        def caption(dev_id, name):
            shown = self.service.aliases.get(dev_id) or name

            if self.service.trust.is_trusted(dev_id):
                return f"{shown}  ({self.texts['net_trusted_mark']})"

            return shown

        for dev_id, meta in rows:
            item = QListWidgetItem(caption(dev_id, clean_name(meta.get("name"))))
            item.setData(Qt.UserRole, dev_id)
            item.setData(Qt.UserRole + 1, clean_name(meta.get("name")))
            listing.addItem(item)

        layout.addWidget(listing)

        buttons = QDialogButtonBox()
        untrust = buttons.addButton(
            self.texts["net_untrust"], QDialogButtonBox.ActionRole
        )
        unpair = buttons.addButton(
            self.texts["net_unpair"], QDialogButtonBox.ActionRole
        )
        close = buttons.addButton(
            self.texts["close"], QDialogButtonBox.RejectRole
        )

        def do_untrust():
            item = listing.currentItem()

            if not item:
                return

            dev_id = item.data(Qt.UserRole)
            self.service.trust.untrust(dev_id)
            item.setText(caption(dev_id, item.data(Qt.UserRole + 1)))
            self._reload_peers()

        def do_unpair():
            item = listing.currentItem()

            if not item:
                return

            dev_id = item.data(Qt.UserRole)
            self.service.trust.untrust(dev_id)
            self.service.pairs.remove(dev_id)
            listing.takeItem(listing.row(item))
            self._reload_peers()
            self._load_videos()

        untrust.clicked.connect(do_untrust)
        unpair.clicked.connect(do_unpair)
        close.clicked.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()


class UnavailableTab(QWidget):
    """네트워크 탭을 쓸 수 없을 때 대신 보여 주는 안내."""

    def __init__(self, parent, texts, message=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addStretch()

        label = QLabel(message or texts["net_no_zeroconf"])
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        layout.addStretch()
