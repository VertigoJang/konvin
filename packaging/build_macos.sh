#!/usr/bin/env bash
# ============================================
#  Konvin - macOS 앱 번들 빌드
#
#  리포 루트에서 실행:
#      packaging/build_macos.sh
# ============================================

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f "scripts/konvin.py" ]; then
    echo "scripts/konvin.py 를 찾을 수 없습니다."
    echo "리포 루트에서 실행하고 있는지 확인하세요."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "가상 환경이 없습니다. 먼저 아래를 실행하세요."
    echo "    python3 -m venv .venv"
    echo "    source .venv/bin/activate"
    echo "    pip install -r requirements-gui.txt"
    exit 1
fi

PY=.venv/bin/python

echo
echo "[1/4] 빌드 도구 설치"
"$PY" -m pip install --quiet --upgrade pyinstaller certifi

echo
echo "[2/4] 아이콘 준비"

if [ -f "assets/konvin.icns" ]; then
    echo "    이미 있음, 건너뜀"
else
    ICONSET=$(mktemp -d)/konvin.iconset
    mkdir -p "$ICONSET"

    for size in 16 32 64 128 256 512; do
        sips -z $size $size assets/konvin.png \
            --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z $double $double assets/konvin.png \
            --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done

    iconutil -c icns "$ICONSET" -o assets/konvin.icns
    echo "    assets/konvin.icns 생성"
fi

echo
echo "[3/4] yt-dlp 내려받기"
mkdir -p packaging/vendor

if [ -f "packaging/vendor/yt-dlp" ]; then
    echo "    이미 있음, 건너뜀"
    echo "    최신판을 쓰려면 packaging/vendor/yt-dlp 를 지우고 다시 실행하세요."
else
    echo "    github.com/yt-dlp/yt-dlp 에서 받는 중..."

    # 인텔과 애플 실리콘 모두에서 도는 빌드
    curl -L --fail --progress-bar \
        -o packaging/vendor/yt-dlp \
        https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos

    chmod +x packaging/vendor/yt-dlp
    echo "    packaging/vendor/yt-dlp 준비"
fi

echo
echo "[4/4] 빌드 (몇 분 걸립니다)"
"$PY" -m PyInstaller --noconfirm --clean packaging/konvin_macos.spec

echo
echo "============================================"
echo " 완료: dist/Konvin.app"
echo "============================================"
echo
ls -la dist/
echo
echo "실행:  open dist/Konvin.app"
echo
echo "처음 실행할 때 '확인되지 않은 개발자' 경고가 뜨면"
echo "Finder 에서 우클릭 후 '열기' 를 고르면 됩니다."
