#!/usr/bin/env python3
"""
Konvin 스모크 테스트 — 화면 없이(headless) 핵심 UI 요소와 문자열이
멀쩡한지 빠르게 확인한다.

정식 유닛 테스트가 아니라, 리팩토링이나 일괄 패치(packaging/patch_*.py)
이후에 "창이 뜨긴 하는가, 쓰이는 문자열이 다 있는가" 정도만 본다.
빌드 전에 한 번 돌려서 실패하면 빌드를 멈추는 용도.

실행:
    QT_QPA_PLATFORM=offscreen python3 scripts/smoke_test.py
"""

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

failures = []


def check(label, condition, detail=""):
    status = "OK " if condition else "FAIL"
    line = f"[{status}] {label}"
    if not condition and detail:
        line += f" — {detail}"
    print(line)
    if not condition:
        failures.append(label)


def collect_referenced_keys(source):
    """코드가 실제로 참조하는 문자열 키를 모은다.

    tr_("key", ...) 는 줄바꿈되는 경우가 있어 여는 괄호 뒤의 공백과
    줄바꿈을 허용하고, 작은따옴표와 큰따옴표를 모두 인정한다.
    """
    referenced = set()

    for pattern in (
        r"""texts\[\s*['"]([a-z0-9_]+)['"]\s*\]""",
        r"""tr_\(\s*['"]([a-z0-9_]+)['"]""",
    ):
        referenced.update(re.findall(pattern, source, re.MULTILINE))

    return referenced


def check_texts_complete(konvin):
    """코드가 참조하는 문자열 키가 모든 언어에 다 있는지."""
    source = (ROOT / "scripts" / "konvin.py").read_text(encoding="utf-8")

    referenced = collect_referenced_keys(source)

    for lang, table in konvin.TEXTS.items():
        missing = sorted(k for k in referenced if k not in table)
        check(
            f"'{lang}' 문자열 누락 없음",
            not missing,
            f"없는 키: {', '.join(missing)}" if missing else "",
        )


def check_texts_unused(konvin):
    """쓰이지 않는 문자열이 남아있지 않은지 (경고만, 실패 아님)."""
    source = (ROOT / "scripts" / "konvin.py").read_text(encoding="utf-8")

    # 동적으로 조립되는 키는 접두사로 예외 처리한다
    dynamic_prefixes = (
        "aspect_", "codec_", "filename_", "device_", "quality_",
        "folder_", "path_", "tab_", "language_name",
    )
    # format() 인자로만 쓰이는 키들
    format_only = {
        "converted", "skipped", "failed", "aborted", "credit",
        "url", "level", "hours", "minutes", "seconds", "home",
    }

    referenced = collect_referenced_keys(source)

    table = konvin.TEXTS["ko"]
    unused = [
        k for k in table
        if k not in referenced
        and not k.startswith(dynamic_prefixes)
        and k not in format_only
    ]

    if unused:
        print(f"[경고] 쓰이지 않는 문자열 {len(unused)}개: {', '.join(sorted(unused))}")
    else:
        print("[OK ] 쓰이지 않는 문자열 없음")


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    import konvin

    texts = konvin.TEXTS["ko"]

    # --- 주요 창이 실제로 만들어지는지 ---
    check("CleanupDialog 생성", konvin.CleanupDialog(None, texts) is not None)
    check(
        "UpdateDialog 생성 (릴리스 노트 포함)",
        konvin.UpdateDialog(None, texts, "v99.0", "테스트 노트") is not None,
    )
    check("HelpDialog 생성", konvin.HelpDialog(None, "ko") is not None)

    # --- 메인 창과 하단 버튼들 ---
    window = konvin.MainWindow()
    check("MainWindow 생성", window is not None)
    check("cleanup_button 존재", hasattr(window, "cleanup_button"))
    check("folder_button 존재", hasattr(window, "folder_button"))
    check("help_button 존재", hasattr(window, "help_button"))

    # --- 중복 다운로드 확인 기능이 살아있는지 (v3.3 설계) ---
    check("read_archive_ids 존재", hasattr(konvin, "read_archive_ids"))
    check("remove_archive_ids 존재", hasattr(konvin, "remove_archive_ids"))
    check("extract_video_id 존재", hasattr(konvin, "extract_video_id"))
    check("IdResolver 존재", hasattr(konvin, "IdResolver"))

    # --- 문자열 무결성 ---
    check_texts_complete(konvin)
    check_texts_unused(konvin)

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        sys.exit(1)

    print("전부 통과.")
    sys.exit(0)


if __name__ == "__main__":
    main()
