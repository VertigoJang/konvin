#!/usr/bin/env python3
"""
Konvin v4 2단계 — 발견한 상대에게 영상 목록을 받아오는 실험용 CLI.

1단계(net_discover.py)에 로컬 HTTP 서버를 얹었다. 각 인스턴스가
자기 changedv 폴더를 훑어 목록을 내주고, 발견한 상대에게 그 목록을
요청해 화면에 찍는다.

아직 인증도 승인 절차도 없다. 같은 네트워크에서 연결이 실제로 되는지,
목록이 오가는지만 본다. 승인 절차는 3단계에서 붙인다.

실행:
    python3 scripts/net_library.py --name "맥북"
    python3 scripts/net_library.py --name "맥북" --folder ~/Movies/Konvin/changedv

명령 (실행 중에 입력):
    list          지금까지 발견한 컴퓨터 보기
    get <번호>    그 컴퓨터의 영상 목록 받아오기
    mine          내가 내주고 있는 목록 보기
    quit          종료

필요한 패키지:
    pip install zeroconf
"""

import argparse
import json
import socket
import sys
import threading
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVICE_TYPE = "_konvin._tcp.local."
ID_FILE = Path.home() / ".konvin_device_id"

# 목록에 넣을 확장자
VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}


# ============================================
# 이 컴퓨터에 관한 것
# ============================================

def device_id():
    """이 컴퓨터를 가리키는 고정 UUID."""
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
    """바깥으로 나갈 때 쓰는 랜 주소. 실제로 연결하지는 않는다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def default_folder():
    """실제 앱이 변환 결과를 두는 곳. konvin.py 의 규칙을 따라간다."""
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


# ============================================
# 내가 내주는 목록
# ============================================

class Library:
    """폴더를 훑어 목록을 만든다.

    바깥에서 들어온 id 를 파일 경로에 직접 쓰지 않으려고, 목록을 만들 때
    id → 경로 대응표를 따로 들고 있는다.
    """

    def __init__(self, folder):
        self.folder = Path(folder).expanduser()
        self.by_id = {}

    def scan(self):
        self.by_id = {}
        items = []

        if not self.folder.is_dir():
            return items

        for path in sorted(self.folder.iterdir()):
            if not path.is_file():
                continue

            if path.suffix.lower() not in VIDEO_SUFFIXES:
                continue

            try:
                stat = path.stat()
            except OSError:
                continue

            # 이름에서 만든 고정 id. 같은 파일이면 매번 같은 값이 나온다.
            file_id = uuid.uuid5(uuid.NAMESPACE_URL, path.name).hex[:12]

            self.by_id[file_id] = path
            items.append({
                "id": file_id,
                "title": path.stem,
                "filename": path.name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            })

        return items

    def path_for(self, file_id):
        """id 에 해당하는 실제 경로. 모르는 id 면 None."""
        return self.by_id.get(file_id)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


# ============================================
# HTTP 서버
# ============================================

class Handler(BaseHTTPRequestHandler):

    library = None
    my_name = ""
    my_id = ""

    def log_message(self, fmt, *args):
        # 기본 로그는 시끄러워서 쓸 만한 것만 직접 찍는다
        print(f"    (요청 받음: {self.client_address[0]} → {self.path})")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/videos":
            self._send_json({
                "device": {"name": self.my_name, "id": self.my_id},
                "videos": self.library.scan(),
            })
            return

        self._send_json({"error": "없는 경로입니다"}, status=404)


def start_server(library, name, my_id):
    """빈 포트에 HTTP 서버를 띄우고 (서버, 포트) 를 준다."""
    Handler.library = library
    Handler.my_name = name
    Handler.my_id = my_id

    server = ThreadingHTTPServer(("", 0), Handler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, port


# ============================================
# 상대에게 목록 받아오기
# ============================================

def fetch_videos(address, port, timeout=5):
    url = f"http://{address}:{port}/videos"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# ============================================
# 발견
# ============================================

class Watcher:

    def __init__(self, my_id):
        self.my_id = my_id
        self.peers = {}       # 서비스 이름 → 정보
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

def show_videos(payload):
    device = payload.get("device", {})
    videos = payload.get("videos", [])

    print(f"  {device.get('name', '(이름 없음)')} 의 영상 {len(videos)}개")

    if not videos:
        print("    (비어 있습니다)")
        return

    for v in videos:
        print(f"    - {v['filename']}  {human_size(v['size'])}")


def main():
    parser = argparse.ArgumentParser(
        description="같은 네트워크의 Konvin 라이브러리를 주고받는 실험용 도구"
    )
    parser.add_argument("--name", default=socket.gethostname(),
                        help="다른 컴퓨터에 보일 이름 (기본값: 호스트명)")
    parser.add_argument("--folder", default=None,
                        help="내줄 영상 폴더 (기본값: Konvin 의 changedv)")
    args = parser.parse_args()

    try:
        from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
    except ImportError:
        print("zeroconf 패키지가 없습니다. 먼저 설치하세요.")
        print("    pip install zeroconf")
        return 1

    my_id = device_id()
    ip = local_ip()
    folder = Path(args.folder).expanduser() if args.folder else default_folder()

    library = Library(folder)
    mine = library.scan()

    server, port = start_server(library, args.name, my_id)

    print(f"이 컴퓨터: {args.name}")
    print(f"기기 ID  : {my_id}")
    print(f"랜 주소  : {ip}:{port}")
    print(f"내줄 폴더: {folder}")
    print(f"           영상 {len(mine)}개" if folder.is_dir()
          else "           (폴더가 없습니다)")
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

    print("찾는 중... 명령: list / get <번호> / mine / quit")
    print()

    try:
        while True:
            try:
                line = input("  > ").strip()
            except EOFError:
                break

            if not line:
                continue

            if line in ("quit", "exit", "q"):
                break

            if line == "mine":
                show_videos({
                    "device": {"name": args.name},
                    "videos": library.scan(),
                })
                continue

            if line == "list":
                peers = watcher.listed()

                if not peers:
                    print("    아직 찾은 컴퓨터가 없습니다.")
                    continue

                for i, p in enumerate(peers, 1):
                    print(f"    {i}. {p['name']}  {p['address']}:{p['port']}")
                continue

            if line.startswith("get"):
                parts = line.split()
                peers = watcher.listed()

                if len(parts) < 2 or not parts[1].isdigit():
                    print("    사용법: get <번호>   (번호는 list 로 확인)")
                    continue

                index = int(parts[1]) - 1

                if index < 0 or index >= len(peers):
                    print("    그런 번호가 없습니다.")
                    continue

                peer = peers[index]
                print(f"    {peer['name']} 에게 목록을 요청합니다...")

                try:
                    payload = fetch_videos(peer["address"], peer["port"])
                except urllib.error.URLError as e:
                    print(f"    연결하지 못했습니다: {e.reason}")
                    print("    (방화벽이나 네트워크 격리를 의심해 보세요)")
                    continue
                except Exception as e:
                    print(f"    실패: {e}")
                    continue

                show_videos(payload)
                continue

            print("    모르는 명령입니다. list / get <번호> / mine / quit")

    except KeyboardInterrupt:
        print()
    finally:
        zc.unregister_service(info)
        zc.close()
        server.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
