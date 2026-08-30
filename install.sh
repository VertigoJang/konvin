#!/usr/bin/env bash
#
# Konvin 설치 스크립트 (사용자 홈에 설치, root 권한 불필요)
#
#   ./install.sh          설치
#   ./install.sh --remove  제거
#
# 하는 일:
#   ~/.local/bin/konvin              실행 명령
#   ~/.local/share/applications/     앱 메뉴 등록
#   ~/.local/share/icons/            아이콘

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"

BIN_PATH="$BIN_DIR/konvin"
DESKTOP_PATH="$APP_DIR/konvin.desktop"
ICON_PATH="$ICON_DIR/konvin.png"


remove() {
    rm -f "$BIN_PATH" "$DESKTOP_PATH" "$ICON_PATH"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APP_DIR" 2>/dev/null || true
    fi

    echo "Konvin 을 제거했습니다."
    echo "설정과 영상은 ~/Konvin 에 그대로 있습니다. 필요 없으면 직접 지우세요."
}


install_konvin() {
    if [ ! -f "$ROOT/konvin.sh" ]; then
        echo "konvin.sh 를 찾을 수 없습니다." >&2
        exit 1
    fi

    chmod +x "$ROOT/konvin.sh"

    mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

    # 리포 위치를 가리키는 실행 명령
    cat > "$BIN_PATH" <<EOF
#!/usr/bin/env bash
exec "$ROOT/konvin.sh" "\$@"
EOF
    chmod +x "$BIN_PATH"

    if [ -f "$ROOT/assets/konvin.png" ]; then
        cp "$ROOT/assets/konvin.png" "$ICON_PATH"
    fi

    cp "$ROOT/konvin.desktop" "$DESKTOP_PATH"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APP_DIR" 2>/dev/null || true
    fi

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi

    echo "설치했습니다."
    echo
    echo "  터미널에서 : konvin"
    echo "  앱 메뉴에서 : Konvin"
    echo

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            echo "참고: $BIN_DIR 가 PATH 에 없습니다."
            echo "아래 줄을 ~/.bashrc 나 ~/.zshrc 에 추가하세요."
            echo
            echo '  export PATH="$HOME/.local/bin:$PATH"'
            echo
            ;;
    esac
}


if [ "${1:-}" = "--remove" ] || [ "${1:-}" = "-r" ]; then
    remove
else
    install_konvin
fi
