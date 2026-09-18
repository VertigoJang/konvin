#!/usr/bin/env python3
"""
Konvin v4 3단계 — 승인을 거쳐 실제로 파일을 받아오는 실험용 CLI.

2단계(net_library.py)에 요청·승인·토큰 흐름을 얹었다.

  1. 받는 쪽이 POST /request 로 파일을 요청한다
  2. 주는 쪽 화면에 "허용할까요?" 가 뜬다 (30초 무응답이면 거부)
  3. 허용하면 일회용 토큰이 나온다 (5분 뒤 만료)
  4. 받는 쪽이 GET /download/<토큰> 으로 파일을 받는다
  5. 토큰은 한 번 쓰면 사라진다

"항상 허용" 을 고르면 그 기기 UUID 가 trusted_devices.json 에 저장되어
다음부터 묻지 않는다.

실행:
    python3 scripts/net_transfer.py --name "맥북"
    python3 scripts/net_transfer.py --name "맥북" --folder ~/some/folder

명령 (실행 중에 입력):
    list            발견한 컴퓨터 보기
    ls <번호>       그 컴퓨터의 영상 목록
    get <번호> <n>  그 컴퓨터의 n 번째 영상 받기
    mine            내가 내주는 목록
    trusted         신뢰 기기 목록
    untrust <번호>  신뢰 해제
    quit            종료

필요한 패키지:
    pip install zeroconf
"""

import argparse
import json
import os
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVICE_TYPE = "_konvin._tcp.local."
ID_FILE = Path.home() / ".konvin_device_id"
TRUSTED_FILE = Path.home() / ".konvin_trusted_devices.json"

VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}

ASK_TIMEOUT = 30        # 확인 창을 몇 초 기다릴지
TOKEN_LIFETIME = 300    # 토큰이 몇 초 뒤 만료되는지


# ============================================
# 이 컴퓨터에 관한 것
# ============================================

def device_id():
    if ID_FILE.exists():
        try:
            saved = ID_FILE.read_text(encoding="utf-8").strip()
            if saved:
                return saved
        except OSError:
            pass

    new = str(uuid.uuid4())

    try:
        ID_FILE.write_text(new, encoding="utf-8")
    except OSError:
        pass

    return new


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def default_folder():
    home = Path.home()

    if sys.platform == "darwin":
        movies = home / "Movies"

        if movies.is_dir():
            return movies / "Konvin" / "changedv"

    if sys.platform == "win32":
        documents = home / "Documents"

        if documents.is_dir():
            return documents / "Konvin" / "changedv"

    return home / "Konvin" / "changedv"


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


# ============================================
# 신뢰 기기 목록
# ============================================

class TrustStore:
    """'항상 허용' 을 고른 기기를 기억한다."""

    def __init__(self, path=TRUSTED_FILE):
        self.path = path
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
            return [(k, v) for k, v in self.devices.items()]


# ============================================
# 내가 내주는 목록
# ============================================

class Library:
    """폴더를 훑어 목록을 만들고, id → 실제 경로 대응표를 들고 있는다.

    바깥에서 들어온 값을 경로에 직접 쓰지 않으려는 장치다.
    """

    def __init__(self, folder):
        self.folder = Path(folder).expanduser()
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

    def path_for(self, file_id):
        with self.lock:
            return self.by_id.get(file_id)

    def info_for(self, file_id):
        path = self.path_for(file_id)

        if not path or not path.is_file():
            return None

        try:
            return {"path": path, "size": path.stat().st_size}
        except OSError:
            return None


# ============================================
# 요청 관리
# ============================================

class RequestDesk:
    """들어온 요청을 붙들고, 사람이 허용할 때까지 기다린다."""

    def __init__(self, trust, asker):
        self.trust = trust
        self.asker = asker          # 화면에 물어보는 함수
        self.requests = {}          # req_id → 상태
        self.tokens = {}            # token → (file_id, 발급 시각)
        self.lock = threading.Lock()

    def submit(self, peer_name, peer_id, file_id, filename, size):
        req_id = secrets.token_urlsafe(9)

        with self.lock:
            self.requests[req_id] = {"state": "대기", "token": None}

        # 이미 믿는 기기면 묻지 않는다
        if self.trust.is_trusted(peer_id):
            self._approve(req_id, file_id)
            print(f"\n  [자동 허용] {peer_name} → {filename}")
            print("  > ", end="", flush=True)
            return req_id, "허용"

        # 사람에게 묻는 건 오래 걸리므로 따로 굴린다
        thread = threading.Thread(
            target=self._ask_then_decide,
            args=(req_id, peer_name, peer_id, file_id, filename, size),
            daemon=True,
        )
        thread.start()

        return req_id, "대기"

    def _ask_then_decide(self, req_id, peer_name, peer_id, file_id, filename, size):
        answer = self.asker(peer_name, filename, size)

        if answer == "always":
            self.trust.trust(peer_id, peer_name)

        if answer in ("yes", "always"):
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
                self.requests[req_id] = {"state": "허용", "token": token}

    def status(self, req_id):
        with self.lock:
            return dict(self.requests.get(req_id, {"state": "없음", "token": None}))

    def take_token(self, token):
        """토큰을 쓰고 없앤다. 만료됐으면 None."""
        with self.lock:
            entry = self.tokens.pop(token, None)

        if not entry:
            return None

        file_id, issued = entry

        if time.time() - issued > TOKEN_LIFETIME:
            return None

        return file_id

    def sweep(self):
        """만료된 토큰을 치운다."""
        now = time.time()

        with self.lock:
            dead = [t for t, (_, at) in self.tokens.items()
                    if now - at > TOKEN_LIFETIME]

            for t in dead:
                del self.tokens[t]


def terminal_asker(peer_name, filename, size):
    """터미널에서 허용 여부를 묻는다. GUI 로 옮길 때 이 함수만 바꾸면 된다."""
    print()
    print("  " + "=" * 52)
    print(f"  다운로드 요청")
    print(f"    {peer_name} 가 다음 파일을 요청했습니다:")
    print(f"    {filename}  ({human_size(size)})")
    print()
    print("    y  허용      n  거부      a  이 컴퓨터는 항상 허용")
    print("    * 항상 허용을 고르면 이후 승인 없이 파일에 자동으로")
    print("      접근할 수 있게 됩니다. 신뢰하는 내 컴퓨터에만 쓰세요.")
    print(f"    ({ASK_TIMEOUT}초 안에 답하지 않으면 거부됩니다)")
    print("  " + "=" * 52)

    answer = {"value": "no"}

    def read():
        try:
            got = input("  허용할까요? [y/n/a] ").strip().lower()
        except EOFError:
            return

        if got in ("y", "yes"):
            answer["value"] = "yes"
        elif got in ("a", "always"):
            answer["value"] = "always"

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    thread.join(timeout=ASK_TIMEOUT)

    if thread.is_alive():
        print("\n  시간이 지나 거부했습니다.")

    label = {"yes": "허용", "always": "항상 허용", "no": "거부"}[answer["value"]]
    print(f"  → {label}")
    print("  > ", end="", flush=True)

    return answer["value"]


# ============================================
# HTTP 서버
# ============================================

class Handler(BaseHTTPRequestHandler):

    library = None
    desk = None
    my_name = ""
    my_id = ""

    def log_message(self, fmt, *args):
        pass    # 필요한 건 직접 찍는다

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- GET ---

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
            self._serve_download(self.path[len("/download/"):])
            return

        self._json({"error": "없는 경로입니다"}, status=404)

    def _serve_download(self, token):
        file_id = self.desk.take_token(token)

        if not file_id:
            self._json({"error": "토큰이 없거나 만료됐습니다"}, status=403)
            return

        info = self.library.info_for(file_id)

        if not info:
            self._json({"error": "파일을 찾을 수 없습니다"}, status=404)
            return

        path, size = info["path"], info["size"]
        print(f"\n  보내는 중: {path.name} ({human_size(size)})")

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.end_headers()

        try:
            with path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile, length=256 * 1024)
        except (OSError, BrokenPipeError, ConnectionResetError) as e:
            print(f"  전송이 끊겼습니다: {e}")
            return

        print(f"  보냈습니다: {path.name}")
        print("  > ", end="", flush=True)

    # --- POST ---

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

        file_id = body.get("file_id", "")
        peer_name = body.get("name", "(이름 없음)")
        peer_id = body.get("id", "")

        self.library.scan()     # 대응표를 최신으로
        info = self.library.info_for(file_id)

        if not info:
            self._json({"error": "그런 파일이 없습니다"}, status=404)
            return

        req_id, state = self.desk.submit(
            peer_name, peer_id, file_id, info["path"].name, info["size"]
        )
        self._json({"request_id": req_id, "state": state})


def start_server(library, desk, name, my_id):
    Handler.library = library
    Handler.desk = desk
    Handler.my_name = name
    Handler.my_id = my_id

    server = ThreadingHTTPServer(("", 0), Handler)
    port = server.server_address[1]

    threading.Thread(target=server.serve_forever, daemon=True).start()

    return server, port


# ============================================
# 상대에게 요청하기
# ============================================

def http_json(url, payload=None, timeout=10):
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url, target, expected_size, timeout=30):
    """파일을 받아 target 에 쓴다. 받은 바이트 수를 돌려준다."""
    request = urllib.request.Request(url)
    tmp = target.with_suffix(target.suffix + ".part")
    got = 0
    last_shown = 0

    with urllib.request.urlopen(request, timeout=timeout) as response:
        with tmp.open("wb") as f:
            while True:
                chunk = response.read(256 * 1024)

                if not chunk:
                    break

                f.write(chunk)
                got += len(chunk)

                if expected_size and got - last_shown > expected_size / 20:
                    last_shown = got
                    percent = got / expected_size * 100
                    print(f"\r    받는 중... {percent:.0f}%  "
                          f"({human_size(got)})", end="", flush=True)

    print()
    tmp.replace(target)

    return got


# ============================================
# 발견
# ============================================

class Watcher:

    def __init__(self, my_id):
        self.my_id = my_id
        self.peers = {}
        self.lock = threading.Lock()

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

        if not found or found["id"] == self.my_id:
            return

        with self.lock:
            self.peers[name] = found

        print(f"\n  [+] {found['name']}  {found['address']}:{found['port']}")
        print("  > ", end="", flush=True)

    def remove_service(self, zc, type_, name):
        with self.lock:
            gone = self.peers.pop(name, None)

        if gone:
            print(f"\n  [-] {gone['name']} — 사라졌습니다")
            print("  > ", end="", flush=True)

    def update_service(self, zc, type_, name):
        pass

    def listed(self):
        with self.lock:
            return list(self.peers.values())


# ============================================

def pick_peer(watcher, arg):
    peers = watcher.listed()

    if not arg.isdigit():
        print("    번호를 숫자로 적어 주세요. (list 로 확인)")
        return None

    index = int(arg) - 1

    if index < 0 or index >= len(peers):
        print("    그런 번호가 없습니다.")
        return None

    return peers[index]


def do_get(peer, video_no, my_name, my_id, save_dir):
    """상대에게 요청을 넣고, 허용되면 받는다."""
    base = f"http://{peer['address']}:{peer['port']}"

    try:
        listing = http_json(f"{base}/videos")
    except urllib.error.URLError as e:
        print(f"    목록을 받지 못했습니다: {e.reason}")
        return

    videos = listing.get("videos", [])

    if video_no < 1 or video_no > len(videos):
        print(f"    1 ~ {len(videos)} 사이의 번호를 적어 주세요.")
        return

    video = videos[video_no - 1]
    print(f"    요청: {video['filename']}  ({human_size(video['size'])})")

    try:
        reply = http_json(f"{base}/request", {
            "file_id": video["id"],
            "name": my_name,
            "id": my_id,
        })
    except urllib.error.HTTPError as e:
        print(f"    거절당했습니다: {e.code}")
        return
    except urllib.error.URLError as e:
        print(f"    연결하지 못했습니다: {e.reason}")
        return

    req_id = reply.get("request_id")
    state = reply.get("state")

    if state == "대기":
        print("    상대의 승인을 기다리는 중...", end="", flush=True)

    # 상태를 주기적으로 확인한다
    token = None
    waited = 0

    while waited < ASK_TIMEOUT + 10:
        try:
            status = http_json(f"{base}/request/{req_id}/status", timeout=5)
        except urllib.error.URLError:
            print("\n    상태를 확인하지 못했습니다.")
            return

        if status.get("state") == "허용":
            token = status.get("token")
            break

        if status.get("state") == "거부":
            print("\n    상대가 거부했습니다.")
            return

        time.sleep(1)
        waited += 1
        print(".", end="", flush=True)

    if not token:
        print("\n    응답이 없어 그만둡니다.")
        return

    print("\n    허용됐습니다. 받기 시작합니다.")

    save_dir.mkdir(parents=True, exist_ok=True)
    target = save_dir / video["filename"]

    if target.exists():
        print(f"    이미 같은 이름의 파일이 있습니다: {target.name}")
        print("    (덮어쓰지 않고 그만둡니다)")
        return

    try:
        got = download_file(
            f"{base}/download/{token}", target, video["size"]
        )
    except urllib.error.HTTPError as e:
        print(f"    받지 못했습니다: {e.code}")
        return
    except urllib.error.URLError as e:
        print(f"    받는 중 끊겼습니다: {e.reason}")
        return

    if got != video["size"]:
        print(f"    크기가 다릅니다. 받은 {got}, 예상 {video['size']}")
        return

    print(f"    다 받았습니다: {target}")


def main():
    parser = argparse.ArgumentParser(
        description="같은 네트워크의 Konvin 에서 승인을 거쳐 파일을 받는 실험용 도구"
    )
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--folder", default=None,
                        help="내줄 영상 폴더 (기본값: Konvin 의 changedv)")
    parser.add_argument("--save-to", default=None,
                        help="받은 파일을 둘 폴더 (기본값: 내줄 폴더와 같음)")
    args = parser.parse_args()

    try:
        from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
    except ImportError:
        print("zeroconf 패키지가 없습니다.  pip install zeroconf")
        return 1

    my_id = device_id()
    ip = local_ip()
    folder = Path(args.folder).expanduser() if args.folder else default_folder()
    save_dir = Path(args.save_to).expanduser() if args.save_to else folder

    library = Library(folder)
    mine = library.scan()

    trust = TrustStore()
    desk = RequestDesk(trust, terminal_asker)

    server, port = start_server(library, desk, args.name, my_id)

    print(f"이 컴퓨터: {args.name}")
    print(f"기기 ID  : {my_id}")
    print(f"랜 주소  : {ip}:{port}")
    print(f"내줄 폴더: {folder}  (영상 {len(mine)}개)")
    print(f"받을 폴더: {save_dir}")
    print(f"신뢰 기기: {len(trust.listed())}대")
    print()

    zc = Zeroconf()
    info = ServiceInfo(
        SERVICE_TYPE,
        f"{args.name}-{my_id[:8]}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={"name": args.name, "id": my_id, "ver": "4.0-experiment"},
    )
    zc.register_service(info)

    watcher = Watcher(my_id)
    ServiceBrowser(zc, SERVICE_TYPE, watcher)

    print("명령: list / ls <번호> / get <번호> <n> / mine / trusted /"
          " untrust <번호> / quit")
    print()

    try:
        while True:
            desk.sweep()

            try:
                line = input("  > ").strip()
            except EOFError:
                break

            if not line:
                continue

            parts = line.split()
            cmd = parts[0]

            if cmd in ("quit", "exit", "q"):
                break

            if cmd == "mine":
                items = library.scan()
                print(f"    내가 내주는 영상 {len(items)}개")

                for i, v in enumerate(items, 1):
                    print(f"      {i}. {v['filename']}  {human_size(v['size'])}")
                continue

            if cmd == "list":
                peers = watcher.listed()

                if not peers:
                    print("    아직 찾은 컴퓨터가 없습니다.")
                    continue

                for i, p in enumerate(peers, 1):
                    mark = " (신뢰함)" if trust.is_trusted(p["id"]) else ""
                    print(f"    {i}. {p['name']}  {p['address']}:{p['port']}{mark}")
                continue

            if cmd == "trusted":
                rows = trust.listed()

                if not rows:
                    print("    신뢰하는 기기가 없습니다.")
                    continue

                for i, (dev_id, meta) in enumerate(rows, 1):
                    print(f"    {i}. {meta.get('name', '(이름 없음)')}  {dev_id}")
                continue

            if cmd == "untrust":
                rows = trust.listed()

                if len(parts) < 2 or not parts[1].isdigit():
                    print("    사용법: untrust <번호>   (trusted 로 확인)")
                    continue

                index = int(parts[1]) - 1

                if index < 0 or index >= len(rows):
                    print("    그런 번호가 없습니다.")
                    continue

                dev_id, meta = rows[index]
                trust.untrust(dev_id)
                print(f"    신뢰를 해제했습니다: {meta.get('name', dev_id)}")
                continue

            if cmd == "ls":
                if len(parts) < 2:
                    print("    사용법: ls <번호>")
                    continue

                peer = pick_peer(watcher, parts[1])

                if not peer:
                    continue

                try:
                    listing = http_json(
                        f"http://{peer['address']}:{peer['port']}/videos"
                    )
                except urllib.error.URLError as e:
                    print(f"    연결하지 못했습니다: {e.reason}")
                    continue

                videos = listing.get("videos", [])
                print(f"    {peer['name']} 의 영상 {len(videos)}개")

                for i, v in enumerate(videos, 1):
                    print(f"      {i}. {v['filename']}  {human_size(v['size'])}")
                continue

            if cmd == "get":
                if len(parts) < 3 or not parts[2].isdigit():
                    print("    사용법: get <컴퓨터 번호> <영상 번호>")
                    continue

                peer = pick_peer(watcher, parts[1])

                if not peer:
                    continue

                do_get(peer, int(parts[2]), args.name, my_id, save_dir)
                continue

            print("    모르는 명령입니다.")

    except KeyboardInterrupt:
        print()
    finally:
        zc.unregister_service(info)
        zc.close()
        server.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
