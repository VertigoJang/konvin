#!/usr/bin/env python3
"""
Konvin 자동 업데이트.

새 버전을 내려받아 자기 자신을 갈아 끼우고 다시 켠다.

## 왜 도우미 스크립트를 쓰나

돌고 있는 프로그램은 자기 파일을 지우거나 덮어쓸 수 없다. 윈도우는 아예
막아 두고, macOS 는 앱 번들 안쪽을 바꾸면 돌던 프로그램이 이상해진다.
그래서 이렇게 한다.

    1. 새 버전을 임시 폴더에 받는다
    2. "이 프로그램이 꺼지면 갈아 끼우고 다시 켜라" 는 작은 스크립트를 만든다
    3. 그 스크립트를 따로 띄워 두고 프로그램을 끈다
    4. 스크립트가 교체를 마치고 새 버전을 켠다

## macOS 에서 ditto 를 쓰는 이유

앱 번들 안에는 심볼릭 링크가 많다 (Qt 프레임워크의 Versions/Current 같은
것들). 파이썬 zipfile 로 풀면 링크가 일반 파일로 바뀌고 실행 권한도 날아가
앱이 망가진다. macOS 에 기본으로 있는 ditto 는 이런 것들을 그대로 살린다.

## 안 되는 경우

소스에서 바로 돌릴 때와 리눅스는 이 기능을 쓰지 않는다. 리눅스는 저장소를
받아 쓰는 방식이라 git pull 이 곧 업데이트다.
"""

import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_FROZEN = getattr(sys, "frozen", False)

CHUNK = 256 * 1024


def ssl_context():
    """macOS 의 파이썬은 시스템 인증서를 쓰지 않아 검증이 실패한다.

    konvin.py 와 같은 방식으로 certifi 의 인증서를 쓴다. 이걸 빼먹으면
    CERTIFICATE_VERIFY_FAILED 로 내려받기가 막힌다.
    """
    try:
        import certifi
        import ssl

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


# ============================================
# 이 설치본에 대해
# ============================================

def target_path():
    """갈아 끼울 대상. macOS 는 앱 번들, 윈도우는 exe."""
    if not IS_FROZEN:
        return None

    exe = Path(sys.executable).resolve()

    if IS_MACOS:
        # .../Konvin.app/Contents/MacOS/Konvin → .../Konvin.app
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent

        return None

    if IS_WINDOWS:
        return exe

    return None


def self_update_supported():
    """자동 업데이트가 가능한지와, 안 되면 그 이유."""
    if not IS_FROZEN:
        return False, "source"

    if not (IS_MACOS or IS_WINDOWS):
        return False, "platform"

    target = target_path()

    if not target:
        return False, "unknown"

    # 쓸 수 있는 자리인지 (관리자 권한이 필요한 위치면 못 바꾼다)
    probe = target.parent

    if not os.access(probe, os.W_OK):
        return False, "readonly"

    return True, ""


def asset_for_release(release):
    """이 운영체제에 맞는 첨부 파일을 고른다."""
    for asset in release.get("assets", []):
        name = asset.get("name", "").lower()

        if IS_MACOS and name.endswith(".zip") and "macos" in name:
            return asset

        if IS_WINDOWS and name.endswith(".exe"):
            return asset

    return None


# ============================================
# 내려받기
# ============================================

class Downloader(QThread):
    """릴리스를 찾아 첨부 파일을 임시 폴더에 받는다."""

    progress = Signal(int, str)     # 퍼센트, 설명
    done = Signal(bool, str)        # 성공 여부, 받은 경로 또는 오류

    def __init__(self, release_api, user_agent, parent=None):
        super().__init__(parent)
        self.release_api = release_api
        self.user_agent = user_agent
        self._stop = False
        self.folder = None

    def cancel(self):
        self._stop = True

    def run(self):
        request = urllib.request.Request(
            self.release_api,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/vnd.github+json",
            },
        )

        try:
            with urllib.request.urlopen(
                request, timeout=15, context=ssl_context()
            ) as response:
                release = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            self.done.emit(False, str(e))
            return

        asset = asset_for_release(release)

        if not asset:
            self.done.emit(False, "no-asset")
            return

        url = asset.get("browser_download_url")
        expected = int(asset.get("size", 0))
        name = asset.get("name", "konvin-update")

        self.folder = Path(tempfile.mkdtemp(prefix="konvin-update-"))
        target = self.folder / name

        self.progress.emit(0, name)

        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": self.user_agent}
            )

            with urllib.request.urlopen(
                request, timeout=30, context=ssl_context()
            ) as response:
                got = 0

                with target.open("wb") as f:
                    while True:
                        if self._stop:
                            self.done.emit(False, "cancelled")
                            return

                        chunk = response.read(CHUNK)

                        if not chunk:
                            break

                        f.write(chunk)
                        got += len(chunk)

                        if expected:
                            self.progress.emit(int(got / expected * 100), name)
        except Exception as e:
            self.done.emit(False, str(e))
            return

        if expected and got != expected:
            self.done.emit(False, f"size-mismatch:{got}:{expected}")
            return

        self.done.emit(True, str(target))


# ============================================
# 갈아 끼우기
# ============================================

def _unpack_macos(archive, into):
    """앱 번들을 푼다. 심볼릭 링크와 권한을 살려야 해서 ditto 를 쓴다."""
    subprocess.run(
        ["ditto", "-x", "-k", str(archive), str(into)],
        check=True,
        capture_output=True,
    )

    for path in into.iterdir():
        if path.suffix == ".app":
            return path

    raise RuntimeError("앱 번들을 찾지 못했습니다")


def _helper_unix(pid, new_path, target, workdir):
    """켜져 있던 프로그램이 꺼지면 갈아 끼우고 다시 켜는 스크립트."""
    script = workdir / "konvin-update.sh"

    script.write_text(
        "#!/bin/bash\n"
        "# Konvin 자동 업데이트 도우미. 교체가 끝나면 스스로 지워진다.\n"
        f"for _ in $(seq 1 120); do\n"
        f'    kill -0 {pid} 2>/dev/null || break\n'
        "    sleep 0.5\n"
        "done\n"
        "sleep 1\n"
        f'rm -rf "{target}"\n'
        f'ditto "{new_path}" "{target}" || exit 1\n'
        f'open "{target}"\n'
        f'rm -rf "{workdir}"\n',
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    return script


def _helper_windows(pid, new_path, target, workdir):
    script = workdir / "konvin-update.bat"

    script.write_text(
        "@echo off\n"
        "rem Konvin 자동 업데이트 도우미\n"
        ":wait\n"
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul\n'
        "if not errorlevel 1 (\n"
        "    timeout /t 1 /nobreak >nul\n"
        "    goto wait\n"
        ")\n"
        "timeout /t 1 /nobreak >nul\n"
        f'move /Y "{new_path}" "{target}" >nul\n'
        f'start "" "{target}"\n',
        encoding="utf-8",
    )

    return script


def install_and_restart(downloaded):
    """받은 파일로 갈아 끼우고 다시 켠다.

    성공하면 도우미를 띄운 뒤 True 를 준다. 부르는 쪽이 곧바로 프로그램을
    꺼야 도우미가 교체를 시작할 수 있다.
    """
    downloaded = Path(downloaded)
    target = target_path()

    if not target:
        return False, "unknown"

    workdir = downloaded.parent
    pid = os.getpid()

    try:
        if IS_MACOS:
            unpacked = workdir / "unpacked"
            unpacked.mkdir(exist_ok=True)
            new_path = _unpack_macos(downloaded, unpacked)
            script = _helper_unix(pid, new_path, target, workdir)
            command = ["/bin/bash", str(script)]
        elif IS_WINDOWS:
            script = _helper_windows(pid, downloaded, target, workdir)
            command = ["cmd", "/c", str(script)]
        else:
            return False, "platform"
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode("utf-8", "replace")[:200]
    except Exception as e:
        return False, str(e)

    try:
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }

        if IS_WINDOWS:
            # 창을 띄우지 않고, 이 프로그램이 꺼져도 살아 있게 한다
            kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(command, **kwargs)
    except Exception as e:
        return False, str(e)

    return True, ""
