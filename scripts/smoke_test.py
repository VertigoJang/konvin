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


def all_sources():
    """scripts 안의 파이썬 파일을 모두 이어 붙인다.

    문자열은 konvin.py 에 모여 있지만 쓰는 쪽은 konvin_net.py 처럼
    다른 모듈일 수 있어서, 한 파일만 보면 안 쓰는 것으로 오해한다.
    """
    chunks = []

    for path in sorted((ROOT / "scripts").glob("*.py")):
        # 이 파일 자체는 건너뛴다. 설명 안의 예시가 실제 참조로 잡힌다.
        if path.name == "smoke_test.py":
            continue

        chunks.append(path.read_text(encoding="utf-8"))

    return "\n".join(chunks)


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
    source = all_sources()

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
    source = all_sources()

    # 동적으로 조립되는 키는 접두사로 예외 처리한다
    dynamic_prefixes = (
        "aspect_", "codec_", "filename_", "device_", "quality_",
        "folder_", "path_", "tab_", "language_name",
        # 이유에 따라 골라 쓰는 키라 이름이 코드에 그대로 나오지 않는다
        "update_manual_",
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

    # --- 네트워크 모듈 (v4) ---
    try:
        import konvin_net
        check("konvin_net 모듈 불러오기", True)
        check("NetService 존재", hasattr(konvin_net, "NetService"))
        check("NetworkTab 존재", hasattr(konvin_net, "NetworkTab"))
        check("ApprovalDialog 존재", hasattr(konvin_net, "ApprovalDialog"))
        check("Fetcher 존재", hasattr(konvin_net, "Fetcher"))
        check("TrustStore 존재", hasattr(konvin_net, "TrustStore"))
        check("PairStore 존재", hasattr(konvin_net, "PairStore"))
        check("Pairer 존재", hasattr(konvin_net, "Pairer"))
        check("cryptography 사용 가능", konvin_net.crypto_available())

        # 네트워크 공유는 기본으로 꺼져 있어 MainWindow 만으로는 탭이 만들어지지
        # 않는다. 서비스를 시작하지 않은 채로 탭과 창을 직접 만들어 본다.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            service = konvin_net.NetService(
                tmp, "smoke", "smoke-0000", Path(tmp) / "trusted.json",
                Path(tmp) / "alias.json",
            )
            texts = konvin.TEXTS["ko"]
            tab = konvin_net.NetworkTab(None, texts, service, tmp)
            check("NetworkTab 생성", tab is not None)
            check("PairCodeDialog 생성",
                  konvin_net.PairCodeDialog(tab, texts, "x") is not None)
            check("PairApproveDialog 생성",
                  konvin_net.PairApproveDialog(tab, texts, "x") is not None)
            tab.deleteLater()
        check("페어링 코드가 6자리 숫자",
              len(konvin_net.pairing_code("a", "b", "c", "d")) == 6
              and konvin_net.pairing_code("a", "b", "c", "d").isdigit())
        check("목록에서 경로가 섞인 파일 이름을 걸러 냄",
              konvin_net.clean_listing({"videos": [
                  {"id": "x", "filename": "../../a.m4v", "size": 1},
                  {"id": "y", "filename": "b.m4v", "size": -1},
                  {"id": "z", "filename": "..", "size": 1},
              ]}) == [{"id": "x", "filename": "a.m4v", "size": 1}])
    except ImportError as e:
        check("konvin_net 모듈 불러오기", False, str(e))

    check("네트워크 탭이 붙어 있음", window.tabs.count() == 2)

    # --- 입력 검증과 네트워크 기본값 ---
    check("옵션 모양 입력을 주소로 받지 않음",
          konvin.normalize_url("--exec=x") is None
          and konvin.normalize_url("-o/tmp/x") is None)
    check("주소에 https:// 를 붙여 줌",
          konvin.normalize_url("youtu.be/abc") == "https://youtu.be/abc")
    check("yt-dlp 인자에서 주소 앞에 -- 가 있음",
          konvin.build_ytdlp_args(
              "https://x/y", konvin.TEMPV, False, konvin.DEFAULT_DEVICE
          )[-2:] == ["--", "https://x/y"])
    # load_config() 는 사용자의 실제 설정을 읽으므로 기본값은 소스에서 확인한다
    check("네트워크 공유 기본값이 꺼짐",
          '"network_enabled": False' in Path(konvin.__file__).read_text(encoding="utf-8"))

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
