#!/usr/bin/env python3
"""
konvin.py 에 PyInstaller 번들 지원을 추가한다.

리포 루트에서 실행:
    python packaging/patch_bundle.py
"""

from pathlib import Path

path = Path("scripts/konvin.py")
text = path.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text

    count = text.count(old)

    if count != 1:
        raise SystemExit(f"{label}: {count} 곳에서 발견 (1 이어야 함)")

    text = text.replace(old, new)
    print(f"  {label}")


print("패치 중...")

# --- 1. 버전 ---
replace_once(
    'VERSION  = "v2.8"\nCODENAME = "Generations"',
    'VERSION  = "v2.9"\nCODENAME = "Packaged"',
    "버전 v2.9",
)

# --- 2. 번들 경로 helper ---
replace_once(
    'IS_ARM     = platform.machine().lower() in ("arm64", "aarch64")',
    'IS_ARM     = platform.machine().lower() in ("arm64", "aarch64")\n'
    'IS_FROZEN  = getattr(sys, "frozen", False)\n'
    "\n"
    "\n"
    "def bundle_dir():\n"
    '    """자원이 놓인 폴더.\n'
    "\n"
    "    PyInstaller 로 묶은 실행 파일에서는 임시로 풀린 폴더를, 소스에서 바로\n"
    "    실행할 때는 리포 루트를 가리킨다.\n"
    '    """\n'
    "    if IS_FROZEN:\n"
    "        return Path(sys._MEIPASS)\n"
    "\n"
    "    return Path(__file__).resolve().parent.parent",
    "bundle_dir()",
)

# --- 3. 도구 탐색에 번들 포함 ---
replace_once(
    '''def find_tool(name):
    """PATH → 내려받은 bin 폴더 → 리포의 venv 순으로 찾는다."""
    found = shutil.which(name)

    if found:
        return found

    local = BIN_DIR / tool_filename(name)

    if local.exists():
        return str(local)

    root = Path(__file__).resolve().parent.parent
    venv_bin = root / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
    candidate = venv_bin / tool_filename(name)

    return str(candidate) if candidate.exists() else name''',
    '''def find_tool(name):
    """PATH → 내려받은 bin 폴더 → 함께 묶인 파일 → 리포의 venv 순으로 찾는다."""
    found = shutil.which(name)

    if found:
        return found

    local = BIN_DIR / tool_filename(name)

    if local.exists():
        return str(local)

    bundled = bundle_dir() / tool_filename(name)

    if bundled.exists():
        return str(bundled)

    venv_bin = bundle_dir() / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
    candidate = venv_bin / tool_filename(name)

    return str(candidate) if candidate.exists() else name''',
    "find_tool 번들 탐색",
)

# --- 4. 아이콘 경로 ---
replace_once(
    'icon_path = Path(__file__).resolve().parent.parent / "assets" / "konvin.png"',
    'icon_path = bundle_dir() / "assets" / "konvin.png"',
    "아이콘 경로",
)

path.write_text(text, encoding="utf-8")
print("완료")
