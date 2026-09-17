#!/usr/bin/env python3
"""
Konvin v4 1단계 — 같은 네트워크의 다른 Konvin 을 찾는지 확인하는 실험용 CLI.

아직 앱에 붙이지 않은 독립 스크립트다. 두 대 이상의 컴퓨터에서 동시에
띄워 서로를 찾아내는지만 본다.

실행:
    python3 scripts/net_discover.py                 # 이름 자동(호스트명)
    python3 scripts/net_discover.py --name "거실 PC"
    python3 scripts/net_discover.py --listen-only   # 광고 없이 찾기만

필요한 패키지:
    pip install zeroconf

Ctrl+C 로 끝낸다.
"""

import argparse
import socket
import sys
import time
import uuid
from pathlib import Path

SERVICE_TYPE = "_konvin._tcp.local."

# 기기 UUID 는 한 번 만들어 두고 계속 쓴다. 실제 앱에서는 설정 파일에
# 들어갈 값이라, 여기서도 같은 자리에 저장해 동작을 맞춰 본다.
ID_FILE = Path.home() / ".konvin_device_id"


def device_id():
    """이 컴퓨터를 가리키는 고정 UUID. 없으면 만들어 저장한다."""
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
    """이 컴퓨터가 바깥으로 나갈 때 쓰는 랜 주소.

    실제로 연결하지는 않는다. UDP 소켓에 목적지만 정해 두면 OS 가
    어느 인터페이스를 쓸지 골라 주고, 그 주소를 읽어 온다.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def free_port():
    """비어 있는 포트를 하나 얻는다."""
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Watcher:
    """다른 Konvin 이 나타나고 사라지는 걸 화면에 찍는다."""

    def __init__(self, my_id):
        self.my_id = my_id
        self.seen = {}

    def _describe(self, zc, name):
        from zeroconf import ServiceInfo  # noqa: F401

        info = zc.get_service_info(SERVICE_TYPE, name, timeout=3000)

        if not info:
            return None

        props = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in info.properties.items()
            if k and v
        }
        addresses = [socket.inet_ntoa(a) for a in info.addresses]

        return {
            "이름": props.get("name", "(이름 없음)"),
            "기기 ID": props.get("id", "(없음)"),
            "주소": addresses[0] if addresses else "(없음)",
            "포트": info.port,
        }

    def add_service(self, zc, type_, name):
        found = self._describe(zc, name)

        if not found:
            print(f"  [?] {name} — 정보를 읽지 못했습니다")
            return

        if found["기기 ID"] == self.my_id:
            print(f"  [나] {found['이름']} — 내 광고가 보입니다 (정상)")
            return

        self.seen[name] = found
        print(f"  [+] {found['이름']}  {found['주소']}:{found['포트']}")
        print(f"      기기 ID {found['기기 ID']}")

    def remove_service(self, zc, type_, name):
        gone = self.seen.pop(name, None)
        label = gone["이름"] if gone else name
        print(f"  [-] {label} — 사라졌습니다")

    def update_service(self, zc, type_, name):
        # zeroconf 가 요구하는 자리. 이 실험에서는 할 일이 없다.
        pass


def main():
    parser = argparse.ArgumentParser(
        description="같은 네트워크의 Konvin 을 찾는 실험용 도구"
    )
    parser.add_argument(
        "--name",
        default=socket.gethostname(),
        help="다른 컴퓨터에 보일 이 컴퓨터 이름 (기본값: 호스트명)",
    )
    parser.add_argument(
        "--listen-only",
        action="store_true",
        help="내 광고 없이 찾기만 한다",
    )
    args = parser.parse_args()

    try:
        from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
    except ImportError:
        print("zeroconf 패키지가 없습니다. 먼저 설치하세요.")
        print("    pip install zeroconf")
        return 1

    my_id = device_id()
    ip = local_ip()

    print(f"이 컴퓨터: {args.name}")
    print(f"기기 ID  : {my_id}")
    print(f"랜 주소  : {ip}")
    print()

    zc = Zeroconf()
    info = None

    if not args.listen_only:
        port = free_port()
        # 서비스 이름은 네트워크 안에서 겹치면 안 되므로 UUID 앞부분을 붙인다
        service_name = f"{args.name}-{my_id[:8]}.{SERVICE_TYPE}"

        info = ServiceInfo(
            SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(ip)],
            port=port,
            properties={
                "name": args.name,
                "id": my_id,
                "ver": "4.0-experiment",
            },
        )
        zc.register_service(info)
        print(f"광고 시작 — 포트 {port}")

    print("찾는 중... (Ctrl+C 로 종료)")
    print()

    watcher = Watcher(my_id)
    ServiceBrowser(zc, SERVICE_TYPE, watcher)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print(f"발견한 다른 컴퓨터: {len(watcher.seen)}대")
    finally:
        if info:
            zc.unregister_service(info)
        zc.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
