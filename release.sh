#!/usr/bin/env bash
#
# Konvin 릴리스 — 버전 올리기부터 GitHub 릴리스까지 한 번에.
#
# 사용법:
#     ./release.sh 4.6                       설명 없이
#     ./release.sh 4.6 notes.md              설명을 파일에서 읽어서
#     ./release.sh 4.6 notes.md --dry-run    무엇을 할지 보여주기만
#
# 하는 일:
#     1. 버전 표기를 네 곳에서 한꺼번에 바꾼다
#        (konvin.py, konvin_macos.spec 세 군데, PKGBUILD)
#     2. 커밋하고 태그를 만들어 올린다
#     3. macOS 앱을 빌드하고 zip 으로 묶는다
#     4. GitHub 릴리스를 만들고 파일을 붙인다
#
# 윈도우 exe 는 VM 에서 따로 빌드해야 한다. 공유 폴더에
# Konvin-<버전>-windows.exe 로 두면 이 스크립트가 알아서 같이 올린다.
# 없으면 macOS 것만 올리고 알려 준다.
#
# 미리 필요한 것:  gh auth login 을 한 번 해 두어야 한다.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

WINDOWS_EXE_DIR="$HOME/Documents/vmwin"

# ============================================
# 입력 확인
# ============================================

usage() {
    echo "사용법: ./release.sh <버전> [설명파일] [--dry-run]"
    echo "  예:   ./release.sh 4.6"
    echo "        ./release.sh 4.6 notes.md"
    exit 1
}

[ $# -ge 1 ] || usage

NEW=""
NOTES_FILE=""
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *)
            if [ -z "$NEW" ]; then
                NEW="$arg"
            elif [ -z "$NOTES_FILE" ]; then
                NOTES_FILE="$arg"
            fi
            ;;
    esac
done

if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "버전은 4.6 처럼 적어 주세요. (받은 값: '$NEW')"
    exit 1
fi

if [ -n "$NOTES_FILE" ] && [ ! -f "$NOTES_FILE" ]; then
    echo "설명 파일을 찾을 수 없습니다: $NOTES_FILE"
    exit 1
fi

# ============================================
# 나갈 수 없는 상태인지 먼저 본다
# ============================================

CURRENT=$(grep -m1 'VERSION  = "v' scripts/konvin.py | sed 's/.*"v\(.*\)".*/\1/')

echo
echo "  지금 버전: $CURRENT"
echo "  새 버전  : $NEW"
echo

if [ "$CURRENT" = "$NEW" ]; then
    echo "이미 v$NEW 입니다."
    exit 1
fi

if git rev-parse "v$NEW" >/dev/null 2>&1; then
    echo "v$NEW 태그가 이미 있습니다."
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "gh 명령을 찾을 수 없습니다.  brew install gh"
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub 로그인이 되어 있지 않습니다.  gh auth login"
    exit 1
fi

# 커밋하지 않은 변경이 있으면 함께 올라간다. 미리 알려 준다.
DIRTY=$(git status --porcelain | grep -v '^?? ' || true)

if [ -n "$DIRTY" ]; then
    echo "  아래 변경이 이번 커밋에 함께 들어갑니다:"
    echo "$DIRTY" | sed 's/^/    /'
    echo
fi

WINDOWS_EXE="$WINDOWS_EXE_DIR/Konvin-$NEW-windows.exe"

if [ -f "$WINDOWS_EXE" ]; then
    echo "  윈도우 exe: 찾음"
else
    echo "  윈도우 exe: 없음 — macOS 것만 올립니다"
    echo "              (VM 에서 빌드한 뒤 아래 경로에 두면 함께 올라갑니다)"
    echo "              $WINDOWS_EXE"
fi

echo

if [ "$DRY_RUN" = true ]; then
    echo "--dry-run 이라 여기서 멈춥니다."
    exit 0
fi

read -r -p "  계속할까요? [y/N] " answer

case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "그만둡니다."; exit 0 ;;
esac

# ============================================
# 1. 버전 바꾸기
# ============================================

echo
echo "[1/4] 버전 표기 갱신"

sed -i '' "s/VERSION  = \"v$CURRENT\"/VERSION  = \"v$NEW\"/" scripts/konvin.py
sed -i '' "s/version=\"$CURRENT\"/version=\"$NEW\"/; \
           s/\"CFBundleShortVersionString\": \"$CURRENT\"/\"CFBundleShortVersionString\": \"$NEW\"/; \
           s/\"CFBundleVersion\": \"$CURRENT\"/\"CFBundleVersion\": \"$NEW\"/" \
    packaging/konvin_macos.spec
sed -i '' "s/pkgver=$CURRENT/pkgver=$NEW/" packaging/PKGBUILD

# 네 곳이 다 바뀌었는지 센다. 하나라도 빠지면 빌드와 표시가 어긋난다.
CHANGED=$(grep -c "\"v\?$NEW\"" scripts/konvin.py packaging/konvin_macos.spec 2>/dev/null \
          | awk -F: '{s+=$2} END {print s}')
CHANGED=$((CHANGED + $(grep -c "pkgver=$NEW" packaging/PKGBUILD)))

if [ "$CHANGED" -ne 5 ]; then
    echo "버전 표기가 예상과 다릅니다 (바뀐 곳 $CHANGED, 5 이어야 함)."
    echo "git checkout -- . 로 되돌린 뒤 직접 확인해 주세요."
    exit 1
fi

echo "    konvin.py, konvin_macos.spec(3곳), PKGBUILD"

# ============================================
# 2. 커밋과 태그
# ============================================

echo
echo "[2/4] 커밋과 태그"

git add -A
git commit -q -m "v$NEW"
git push -q
git tag "v$NEW"
git push -q origin "v$NEW"

echo "    v$NEW 태그를 올렸습니다"

# ============================================
# 3. 빌드
# ============================================

echo
echo "[3/4] macOS 빌드"
echo

packaging/build_macos.sh

ZIP="Konvin-$NEW-macos-intel.zip"

cd dist
rm -f Konvin-*.zip
zip -q -r -y "$ZIP" Konvin.app
cd ..

echo
echo "    dist/$ZIP"

# ============================================
# 4. 릴리스
# ============================================

echo
echo "[4/4] GitHub 릴리스"

FILES=("dist/$ZIP")

if [ -f "$WINDOWS_EXE" ]; then
    FILES+=("$WINDOWS_EXE")
fi

if [ -n "$NOTES_FILE" ]; then
    gh release create "v$NEW" "${FILES[@]}" \
        --title "v$NEW" --notes-file "$NOTES_FILE"
else
    gh release create "v$NEW" "${FILES[@]}" \
        --title "v$NEW" --notes "v$NEW"
fi

echo
echo "============================================"
echo " v$NEW 릴리스 완료"
echo "============================================"
echo

if [ ! -f "$WINDOWS_EXE" ]; then
    echo "윈도우 exe 는 빠졌습니다. VM 에서 빌드한 뒤 붙이세요:"
    echo "    gh release upload v$NEW <exe 경로>"
    echo
fi

echo "설치된 앱도 바꾸려면:"
echo "    rm -rf /Applications/Konvin.app"
echo "    cp -R dist/Konvin.app /Applications/"
echo
echo "다른 컴퓨터의 Konvin 은 앱 안에서 알아서 갱신됩니다."
