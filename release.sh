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
#     1. 버전 표기를 다섯 곳에서 한꺼번에 바꾼다
#        (konvin.py, konvin_macos.spec 세 군데, PKGBUILD)
#     2. 설명 파일이 있으면 docs/release-notes/v<버전>.md 로 넣는다
#     3. 커밋하고 태그를 만들어 올린다
#     4. GitHub Actions 가 macOS 와 윈도우 빌드를 돌리고 릴리스에 붙인다
#        (.github/workflows/release.yml)
#
# 빌드는 전부 GitHub 에서 돈다. 이 스크립트는 리눅스·맥·WSL 어디서든 된다.
# 맥이나 윈도우 VM 은 필요 없다.
#
# 미리 필요한 것:  gh auth login 을 한 번 해 두어야 한다.
#                  (git push 용 SSH 키와는 별개다. gh 는 릴리스를 만들고
#                   빌드 상태를 보는 데 쓴다.)

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

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

for tool in gh git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$tool 명령을 찾을 수 없습니다."
        exit 1
    fi
done

if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub 로그인이 되어 있지 않습니다.  gh auth login"
    echo "(git push 용 SSH 키가 있어도 gh 로그인은 따로 해야 합니다.)"
    exit 1
fi

if [ ! -f ".github/workflows/release.yml" ]; then
    echo ".github/workflows/release.yml 이 없습니다."
    echo "빌드를 돌릴 워크플로가 없으면 태그만 올라가고 파일은 붙지 않습니다."
    exit 1
fi

# 커밋하지 않은 변경이 있으면 함께 올라간다. 미리 알려 준다.
DIRTY=$(git status --porcelain | grep -v '^?? ' || true)

if [ -n "$DIRTY" ]; then
    echo "  아래 변경이 이번 커밋에 함께 들어갑니다:"
    echo "$DIRTY" | sed 's/^/    /'
    echo
fi

if [ -n "$NOTES_FILE" ]; then
    echo "  설명: $NOTES_FILE → docs/release-notes/v$NEW.md"
else
    echo "  설명: 없음 — 릴리스에 태그 이름만 적힙니다"
fi

echo "  빌드: GitHub Actions (macOS 인텔 + 윈도우)"
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

# sed -i 는 GNU 와 BSD(맥) 가 서로 달라서 쓰지 않는다.
replace() {
    python3 - "$1" "$2" "$3" <<'EOF'
import pathlib
import sys

path, old, new = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")

if old not in text:
    sys.exit(f"{path} 에서 '{old}' 를 찾을 수 없습니다.")

path.write_text(text.replace(old, new), encoding="utf-8")
EOF
}

replace scripts/konvin.py \
    "VERSION  = \"v$CURRENT\"" "VERSION  = \"v$NEW\""

replace packaging/konvin_macos.spec \
    "version=\"$CURRENT\"" "version=\"$NEW\""
replace packaging/konvin_macos.spec \
    "\"CFBundleShortVersionString\": \"$CURRENT\"" "\"CFBundleShortVersionString\": \"$NEW\""
replace packaging/konvin_macos.spec \
    "\"CFBundleVersion\": \"$CURRENT\"" "\"CFBundleVersion\": \"$NEW\""

replace packaging/PKGBUILD \
    "pkgver=$CURRENT" "pkgver=$NEW"

# 다섯 곳이 다 바뀌었는지 센다. 하나라도 빠지면 빌드와 표시가 어긋난다.
# 워크플로도 같은 검사를 하지만, 태그를 올리기 전에 잡는 쪽이 낫다.
CHANGED=0
CHANGED=$((CHANGED + $(grep -c "VERSION  = \"v$NEW\"" scripts/konvin.py || true)))
CHANGED=$((CHANGED + $(grep -c "\"$NEW\"" packaging/konvin_macos.spec || true)))
CHANGED=$((CHANGED + $(grep -c "pkgver=$NEW" packaging/PKGBUILD || true)))

if [ "$CHANGED" -ne 5 ]; then
    echo "버전 표기가 예상과 다릅니다 (바뀐 곳 $CHANGED, 5 이어야 함)."
    echo "git checkout -- . 로 되돌린 뒤 직접 확인해 주세요."
    exit 1
fi

echo "    konvin.py, konvin_macos.spec(3곳), PKGBUILD"

# ============================================
# 2. 설명 넣기
# ============================================

echo
echo "[2/4] 릴리스 설명"

if [ -n "$NOTES_FILE" ]; then
    mkdir -p docs/release-notes
    cp "$NOTES_FILE" "docs/release-notes/v$NEW.md"
    echo "    docs/release-notes/v$NEW.md"
else
    echo "    건너뜀"
fi

# ============================================
# 3. 커밋과 태그
# ============================================

echo
echo "[3/4] 커밋과 태그"

git add -A
git commit -q -m "v$NEW"
git push -q
git tag "v$NEW"
git push -q origin "v$NEW"

echo "    v$NEW 태그를 올렸습니다"

# ============================================
# 4. CI 지켜보기
# ============================================

echo
echo "[4/4] GitHub Actions"
echo "    빌드가 시작되기를 기다립니다..."

RUN_ID=""

for _ in $(seq 1 20); do
    sleep 5
    RUN_ID=$(gh run list --workflow release.yml --limit 20 \
        --json databaseId,headBranch \
        --jq "[.[] | select(.headBranch == \"v$NEW\")] | first | .databaseId" 2>/dev/null || true)
    [ -n "$RUN_ID" ] && [ "$RUN_ID" != "null" ] && break
    RUN_ID=""
done

if [ -z "$RUN_ID" ]; then
    echo
    echo "    빌드를 찾지 못했습니다. 아래로 직접 확인해 주세요:"
    echo "        gh run list --workflow release.yml"
    exit 0
fi

echo "    빌드 #$RUN_ID — 10 분쯤 걸립니다"
echo

if gh run watch "$RUN_ID" --exit-status; then
    echo
    echo "============================================"
    echo " v$NEW 릴리스 완료"
    echo "============================================"
    echo
    gh release view "v$NEW"
    echo
    echo "다른 컴퓨터의 Konvin 은 앱 안에서 알아서 갱신됩니다."
else
    echo
    echo "빌드가 실패했습니다. 무엇이 틀렸는지 보려면:"
    echo "    gh run view $RUN_ID --log-failed"
    echo
    echo "태그는 이미 올라가 있습니다. 고친 뒤 같은 태그로 다시 돌리려면:"
    echo "    gh workflow run release.yml -f tag=v$NEW"
    exit 1
fi
