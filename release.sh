#!/usr/bin/env bash
#
# Konvin 릴리스 — 버전 올리기부터 GitHub 릴리스까지 한 번에. (리눅스 전용)
#
# 사용법:
#     ./release.sh 4.7
#     ./release.sh 4.7 notes.md
#     ./release.sh 4.7 notes.md --dry-run
#
# 하는 일:
#     1. 버전 표기를 두 곳에서 바꾼다 (scripts/konvin.py, packaging/PKGBUILD)
#     2. 설명 파일이 있으면 docs/release-notes/v<버전>.md 로 넣는다
#     3. 커밋하고 태그를 만들어 올린다
#     4. GitHub Actions(release.yml)가 태그로 릴리스를 만든다
#        (리눅스는 소스 배포라 첨부 바이너리는 없고 노트만 붙는다)
#
#  미리 필요한 것:  gh auth login 을 한 번 해 두어야 한다.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

usage() {
    echo "사용법: ./release.sh <버전> [설명파일] [--dry-run]"
    echo "  예:   ./release.sh 4.7"
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
            if [ -z "$NEW" ]; then NEW="$arg"
            elif [ -z "$NOTES_FILE" ]; then NOTES_FILE="$arg"; fi
            ;;
    esac
done

if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "버전은 4.7 처럼 적어 주세요. (받은 값: '$NEW')"; exit 1
fi

if [ -n "$NOTES_FILE" ] && [ ! -f "$NOTES_FILE" ]; then
    echo "설명 파일을 찾을 수 없습니다: $NOTES_FILE"; exit 1
fi

CURRENT=$(grep -m1 'VERSION  = "v' scripts/konvin.py | sed 's/.*"v\(.*\)".*/\1/')

echo
echo "  지금 버전: $CURRENT"
echo "  새 버전  : $NEW"
echo

if [ "$CURRENT" = "$NEW" ]; then echo "이미 v$NEW 입니다."; exit 1; fi
if git rev-parse "v$NEW" >/dev/null 2>&1; then echo "v$NEW 태그가 이미 있습니다."; exit 1; fi

for tool in gh git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$tool 명령을 찾을 수 없습니다."; exit 1
    fi
done

if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub 로그인이 되어 있지 않습니다.  gh auth login"; exit 1
fi

if [ ! -f ".github/workflows/release.yml" ]; then
    echo ".github/workflows/release.yml 이 없습니다."; exit 1
fi

DIRTY=$(git status --porcelain | grep -v '^?? ' || true)
if [ -n "$DIRTY" ]; then
    echo "  아래 변경이 이번 커밋에 함께 들어갑니다:"
    echo "$DIRTY" | sed 's/^/    /'; echo
fi

if [ -n "$NOTES_FILE" ]; then
    echo "  설명: $NOTES_FILE → docs/release-notes/v$NEW.md"
else
    echo "  설명: 없음 — 릴리스에 태그 이름만 적힙니다"
fi
echo

if [ "$DRY_RUN" = true ]; then echo "--dry-run 이라 여기서 멈춥니다."; exit 0; fi

read -r -p "  계속할까요? [y/N] " answer
case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "그만둡니다."; exit 0 ;;
esac

echo
echo "[1/4] 버전 표기 갱신"

replace() {
    python3 - "$1" "$2" "$3" <<'EOF'
import pathlib, sys
path, old, new = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
if old not in text:
    sys.exit(f"{path} 에서 '{old}' 를 찾을 수 없습니다.")
path.write_text(text.replace(old, new), encoding="utf-8")
EOF
}

replace scripts/konvin.py "VERSION  = \"v$CURRENT\"" "VERSION  = \"v$NEW\""
replace packaging/PKGBUILD "pkgver=$CURRENT" "pkgver=$NEW"

CHANGED=0
CHANGED=$((CHANGED + $(grep -c "VERSION  = \"v$NEW\"" scripts/konvin.py || true)))
CHANGED=$((CHANGED + $(grep -c "pkgver=$NEW" packaging/PKGBUILD || true)))

if [ "$CHANGED" -ne 2 ]; then
    echo "버전 표기가 예상과 다릅니다 (바뀐 곳 $CHANGED, 2 이어야 함)."
    echo "git checkout -- . 로 되돌린 뒤 직접 확인해 주세요."; exit 1
fi

echo "    scripts/konvin.py, packaging/PKGBUILD"

echo
echo "[2/4] 릴리스 설명"
if [ -n "$NOTES_FILE" ]; then
    mkdir -p docs/release-notes
    cp "$NOTES_FILE" "docs/release-notes/v$NEW.md"
    echo "    docs/release-notes/v$NEW.md"
else
    echo "    건너뜀"
fi

echo
echo "[3/4] 커밋과 태그"
git add -A
git commit -q -m "v$NEW"
git push -q
git tag "v$NEW"
git push -q origin "v$NEW"
echo "    v$NEW 태그를 올렸습니다"

echo
echo "[4/4] GitHub Actions"
echo "    릴리스 작업이 시작되기를 기다립니다..."

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
    echo "    작업을 찾지 못했습니다. 직접 확인: gh run list --workflow release.yml"
    exit 0
fi

echo "    작업 #$RUN_ID"
echo

if gh run watch "$RUN_ID" --exit-status; then
    echo
    echo "============================================"
    echo " v$NEW 릴리스 완료"
    echo "============================================"
    echo
    gh release view "v$NEW"
else
    echo
    echo "작업이 실패했습니다. 로그: gh run view $RUN_ID --log-failed"
    echo "태그는 올라가 있습니다. 다시 돌리려면: gh workflow run release.yml -f tag=v$NEW"
    exit 1
fi
