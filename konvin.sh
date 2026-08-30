#!/usr/bin/env bash
#
# Konvin 실행 스크립트
#
# venv 를 알아서 찾아 활성화하고 프로그램을 띄운다.
# 어디서 실행해도 되도록 스크립트 자신의 위치를 기준으로 경로를 잡는다.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
APP="$ROOT/scripts/konvin.py"

if [ ! -f "$APP" ]; then
    echo "konvin.py 를 찾을 수 없습니다: $APP" >&2
    exit 1
fi

# ffmpeg 는 배포판 패키지로 설치해야 한다
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg 가 설치되어 있지 않습니다." >&2
    echo "  Arch   : sudo pacman -S ffmpeg" >&2
    echo "  Debian : sudo apt install ffmpeg" >&2
    echo "  Fedora : sudo dnf install ffmpeg" >&2
    exit 1
fi

# venv 가 없으면 만들고 의존성을 설치한다
if [ ! -d "$VENV" ]; then
    echo "가상 환경을 만드는 중..."
    python3 -m venv "$VENV"

    echo "필요한 패키지를 설치하는 중... (처음 한 번만, 몇 분 걸릴 수 있습니다)"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$ROOT/requirements-gui.txt"
fi

# PySide6 가 빠져 있으면 (venv 는 있는데 설치가 덜 된 경우) 다시 설치
if ! "$VENV/bin/python" -c "import PySide6" >/dev/null 2>&1; then
    echo "필요한 패키지를 설치하는 중..."
    "$VENV/bin/pip" install --quiet -r "$ROOT/requirements-gui.txt"
fi

exec "$VENV/bin/python" "$APP" "$@"
