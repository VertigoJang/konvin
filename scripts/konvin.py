#!/usr/bin/env python3

# ============================================
# Konvin
# Version : v2.8
# Codename: Lineage
#
# Copyright (c) 2026 장현기 (VertigoJang)
# MIT License — see LICENSE
# https://github.com/VertigoJang/konvin
# ============================================

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Konvin"
VERSION  = "v3.0"
CODENAME = "Tidy"

AUTHOR     = "장현기 (VertigoJang)"
COPYRIGHT  = f"Copyright (c) 2026 {AUTHOR}"
REPO_URL   = "https://github.com/VertigoJang/konvin"
ISSUES_URL = "https://github.com/VertigoJang/konvin/issues"
DONATE_URL = "https://buymeacoffee.com/iputaspellonyou"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS   = sys.platform == "darwin"
IS_ARM     = platform.machine().lower() in ("arm64", "aarch64")
IS_FROZEN  = getattr(sys, "frozen", False)


def bundle_dir():
    """자원이 놓인 폴더.

    PyInstaller 로 묶은 실행 파일에서는 임시로 풀린 폴더를, 소스에서 바로
    실행할 때는 리포 루트를 가리킨다.
    """
    if IS_FROZEN:
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


def default_base():
    """작업 폴더 위치.

    윈도우는 파일 이름의 대소문자를 구분하지 않아, 홈에 소스를 konvin 으로
    받아 두면 작업 폴더 Konvin 과 같은 폴더가 되어 버린다. 그래서 윈도우에서는
    문서 폴더 아래에 둔다.
    """
    # 윈도우와 macOS 는 파일 이름의 대소문자를 구분하지 않아, 홈에 소스를
    # konvin 으로 받아 두면 작업 폴더 Konvin 과 같은 폴더가 되어 버린다.
    #
    # macOS 는 문서 폴더가 iCloud 동기화 대상인 경우가 많아 영상 파일이 통째로
    # 올라간다. 그래서 표준 동영상 폴더를 쓴다.
    if IS_MACOS:
        movies = Path.home() / "Movies"

        if movies.is_dir():
            return movies / APP_NAME

    if IS_WINDOWS:
        documents = Path.home() / "Documents"

        if documents.is_dir():
            return documents / APP_NAME

    return Path.home() / APP_NAME


BASE      = default_base()
TEMPV     = BASE / "tempv"
CHANGEDV  = BASE / "changedv"
ARCHIVEV  = BASE / "archivev"
PLAYLISTV = BASE / "playlistv"
BIN_DIR   = BASE / "bin"

ARCHIVE_FILE = BASE / "download_archive.txt"
CONFIG_FILE  = BASE / "config.json"

LEGACY_BASES = [Path.home() / "iPodSync"]

if IS_WINDOWS:
    LEGACY_BASES.append(Path.home() / APP_NAME)

if IS_MACOS:
    # v3.0 까지는 문서 폴더에 두었다
    LEGACY_BASES.append(Path.home() / "Documents" / APP_NAME)


def looks_like_workspace(path):
    """작업 폴더로 보이는지 확인. 소스 폴더를 잘못 옮기지 않기 위한 검사."""
    if not path.is_dir():
        return False

    markers = ("tempv", "changedv", "archivev", "playlistv")
    return any((path / marker).is_dir() for marker in markers)


def migrate_legacy_base():
    """예전 위치에 작업 폴더가 있으면 현재 위치로 옮긴다."""
    if BASE.exists():
        return

    for legacy in LEGACY_BASES:
        if legacy == BASE or not looks_like_workspace(legacy):
            continue

        try:
            BASE.parent.mkdir(parents=True, exist_ok=True)
            legacy.rename(BASE)
        except OSError:
            pass

        return


migrate_legacy_base()

for _d in (TEMPV, CHANGEDV, ARCHIVEV, PLAYLISTV, BIN_DIR):
    _d.mkdir(parents=True, exist_ok=True)

VALID_EXTENSIONS = [".webm", ".mkv", ".mp4", ".avi", ".mov"]
OUTPUT_EXTENSIONS = [".m4v"]


# ============================================
# 외부 도구 찾기
# ============================================

def tool_filename(name):
    return f"{name}.exe" if IS_WINDOWS else name


def find_tool(name):
    """PATH → 내려받은 bin 폴더 → 리포의 venv 순으로 찾는다."""
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

    return str(candidate) if candidate.exists() else name


def tool_available(path):
    """실행 가능한 실제 경로인지 확인."""
    return os.path.sep in path or os.path.isfile(path)


YTDLP   = find_tool("yt-dlp")
FFMPEG  = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def refresh_tools():
    global YTDLP, FFMPEG, FFPROBE
    YTDLP   = find_tool("yt-dlp")
    FFMPEG  = find_tool("ffmpeg")
    FFPROBE = find_tool("ffprobe")


def ffmpeg_ready():
    return tool_available(FFMPEG) and tool_available(FFPROBE)


FFMPEG_SOURCES = {
    "windows": {
        "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "home": "https://www.gyan.dev/ffmpeg/builds/",
        "credit": "gyan.dev",
    },
    "linux": {
        "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "home": "https://johnvansickle.com/ffmpeg/",
        "credit": "John Van Sickle",
    },
    "macos": {
        "url": "https://evermeet.cx/ffmpeg/getrelease/zip",
        "extra_urls": ["https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"],
        "home": "https://evermeet.cx/ffmpeg/",
        "credit": "Helmut K. C. Tessarek",
    },
}


def ffmpeg_source():
    """이 환경에서 쓸 수 있는 내려받기 출처. 없으면 None."""
    if IS_WINDOWS:
        return FFMPEG_SOURCES["windows"]

    if IS_MACOS:
        # 애플 실리콘용 정적 빌드는 안정적인 고정 주소가 없어 Homebrew 를 안내한다
        return None if IS_ARM else FFMPEG_SOURCES["macos"]

    return None if IS_ARM else FFMPEG_SOURCES["linux"]


def package_manager_hint():
    if IS_WINDOWS:
        return "winget install Gyan.FFmpeg"

    if IS_MACOS:
        return "brew install ffmpeg"

    return (
        "Arch      : sudo pacman -S ffmpeg\n"
        "Debian    : sudo apt install ffmpeg\n"
        "Fedora    : sudo dnf install ffmpeg\n"
        "openSUSE  : sudo zypper install ffmpeg"
    )


# ============================================
# 기기 세대별 인코딩 사양
#
# 클릭휠 아이팟은 세대마다 디코딩할 수 있는 H.264 레벨과 비트레이트 상한이
# 다르다. 액정은 모두 320x240 이지만 5.5세대부터는 640x480 까지 디코딩할 수
# 있어, TV 출력을 쓰거나 원본을 덜 깎고 싶을 때 의미가 있다.
# ============================================

DEVICE_PROFILES = {
    "5g": {
        "level": "1.3",
        "width": 320,
        "height": 240,
        "source_height": 480,
        "video_bitrates": {"low": 384, "medium": 600, "high": 768},
    },
    "5.5g": {
        "level": "2.0",
        "width": 640,
        "height": 480,
        "source_height": 720,
        "video_bitrates": {"low": 700, "medium": 1100, "high": 1500},
    },
    "classic": {
        "level": "3.0",
        "width": 640,
        "height": 480,
        "source_height": 720,
        # 상한은 2500 이지만 꽉 채우면 발열과 배터리 소모가 크다.
        # 실사용 권장값인 1500 을 보통으로 둔다.
        "video_bitrates": {"low": 900, "medium": 1500, "high": 2500},
    },
}

AUDIO_BITRATES = {"low": 96, "medium": 128, "high": 160}

VIDEO_CODECS = ("h264", "mpeg4")
ASPECT_MODES = ("letterbox", "preserve")

DEFAULT_DEVICE   = "5g"
DEFAULT_VIDEO    = "medium"
DEFAULT_AUDIO    = "medium"
DEFAULT_CODEC    = "h264"
DEFAULT_ASPECT   = "letterbox"
DEFAULT_LANGUAGE = "ko"

COLLAPSED_HEIGHT = 380
EXPANDED_HEIGHT  = 700

MIT_LICENSE = f"""MIT License

{COPYRIGHT}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


# ============================================
# 다국어 문자열
# ============================================

TEXTS = {
    "ko": {
        "language_name":  "한국어",
        "queue":          "대기열",
        "single_video":   "단일 영상",
        "playlist":       "재생목록",
        "device":         "기기:",
        "video_quality":  "영상:",
        "audio_quality":  "소리:",
        "url_hint":       "유튜브 주소",
        "add":            "추가",
        "remove":         "선택 삭제",
        "clear":          "전체 삭제",
        "start":          "다운로드 후 변환",
        "convert_only":   "기존 파일 변환",
        "stop":           "중지",
        "settings":       "설정",
        "help":           "?",
        "show_log":       "로그 보기",
        "hide_log":       "로그 숨기기",
        "ready":          "준비됨",
        "stopped":        "중지됨",
        "downloading":    "다운로드 중",
        "converting":     "변환 중",
        "file_counter":   "파일 {current}/{total}",
        "eta_calc":       "시간 계산 중",
        "eta_left":       "약 {time} 남음",
        "output_path":    "저장 위치: {path}",
        "no_url":         "주소를 먼저 추가하세요.",
        "no_files":       "변환할 파일이 없습니다.",
        "no_new_files":   "변환할 새 파일이 없습니다.",
        "closing":        "작업이 진행 중입니다. 종료할까요?",

        "device_5g":      "5세대 (2005)",
        "device_5.5g":    "5.5세대 (2006)",
        "device_classic": "6·7세대 클래식",
        "device_5g_tip":
            "iPod with Video. 최대 320×240, 768kbps 까지 재생합니다.",
        "device_5.5g_tip":
            "화면이 밝아진 후기형. 최대 640×480, 1.5Mbps 까지 재생합니다.",
        "device_classic_tip":
            "iPod classic 80/120/160GB. 최대 640×480, 2.5Mbps 까지 재생합니다.",

        "quality_low":    "낮음 ({kbps}k)",
        "quality_medium": "보통 ({kbps}k)",
        "quality_high":   "높음 ({kbps}k)",

        "language":       "언어:",
        "settings_title": "설정",
        "tab_general":    "일반",
        "tab_encoding":   "변환",
        "tab_cleanup":    "정리",
        "tab_paths":      "폴더 위치",
        "tab_about":      "정보",
        "paths":          "폴더 위치",
        "converted":      "변환 완료",
        "skipped":        "건너뜀",
        "failed":         "실패",
        "aborted":        "중단됨",
        "minutes":        "{n}분",
        "seconds":        "{n}초",
        "hours":          "{h}시간 {m}분",
        "done_title":     f"{APP_NAME} — 작업 완료",
        "done_stopped":   f"{APP_NAME} — 중지됨",
        "summary":        "변환 {converted} · 건너뜀 {skipped} · 실패 {failed}",
        "summary_abort":  "변환 {converted} · 건너뜀 {skipped} · 실패 {failed} · 중단 {aborted}",
        "open_folder":    "저장 폴더 열기",
        "help_title":     f"{APP_NAME} 사용 설명",
        "close":          "닫기",

        "aspect":            "화면 비율:",
        "aspect_letterbox":  "화면 채우기 (위아래 검은 띠)",
        "aspect_preserve":   "원본 비율 유지",
        "aspect_hint":
            "아이팟 액정은 4:3 입니다. 화면 채우기는 검은 띠를 넣어 4:3 으로 "
            "맞추고, 원본 비율 유지는 띠 없이 원본 모양 그대로 둡니다. 어느 "
            "쪽이든 기기에서 보이는 모습은 거의 같지만, 비율을 유지하면 파일이 "
            "조금 작아집니다.",

        "codec":          "영상 코덱:",
        "codec_h264":     "H.264 (권장)",
        "codec_mpeg4":    "MPEG-4 (호환용)",
        "codec_hint":
            "H.264 는 같은 용량에서 화질이 더 좋아 대부분의 경우 알맞습니다. "
            "재생이 안 되는 파일이 있다면 MPEG-4 로 바꿔 보세요.",

        "cleanup_folder":  "폴더:",
        "cleanup_delete_selected": "선택 삭제",
        "cleanup_delete_all":      "전체 삭제",
        "cleanup_refresh": "새로 고침",
        "cleanup_empty":   "이 폴더는 비어 있습니다.",
        "cleanup_total":   "파일 {count}개 · {size}",
        "cleanup_confirm_selected":
            "선택한 {count}개 파일({size})을 삭제합니다.\n되돌릴 수 없습니다. 계속할까요?",
        "cleanup_confirm_all":
            "{folder} 폴더의 파일 {count}개({size})를 모두 삭제합니다.\n되돌릴 수 없습니다. 계속할까요?",
        "cleanup_done":    "{count}개 파일을 삭제했습니다.",
        "cleanup_failed":  "{count}개 파일을 삭제하지 못했습니다.",
        "cleanup_nothing_selected": "삭제할 파일을 선택하세요.",
        "cleanup_title":   "파일 정리",
        "cleanup_button":  "파일 정리",
        "record_title":    "다운로드 기록",
        "record_hint":
            "이미 받은 영상의 목록입니다. 같은 영상을 두 번 받지 않게 하려고 "
            "쓰입니다. 폴더에서 파일을 지워도 이 기록은 남아 있어, 다시 받으려면 "
            "여기서 초기화해야 합니다.",
        "record_count":    "기록된 영상 {count}개",
        "record_empty":    "기록이 없습니다.",
        "record_reset":    "기록 초기화",
        "record_confirm":
            "다운로드 기록 {count}개를 지웁니다.\n"
            "이후 같은 영상을 다시 받을 수 있게 됩니다. 계속할까요?",
        "record_done":     "기록을 초기화했습니다.",

        "folder_tempv":     "tempv — 단일 영상 원본",
        "folder_playlistv": "playlistv — 재생목록 원본",
        "folder_changedv":  "changedv — 변환 완료 영상",
        "folder_archivev":  "archivev — 변환 후 보관된 원본",

        "path_tempv":     "단일 영상으로 받은 원본이 임시로 저장됩니다.",
        "path_playlistv": "재생목록으로 받은 원본이 임시로 저장됩니다.",
        "path_changedv":  "변환이 끝난 영상이 저장됩니다. 아이팟에 넣을 파일입니다.",
        "path_archivev":  "변환이 끝난 뒤 원본이 이곳으로 옮겨집니다.",
        "path_bin":       "직접 내려받은 ffmpeg 가 여기에 저장됩니다.",
        "path_archive_file": "이미 받은 영상의 목록입니다. 같은 영상을 두 번 받지 않게 합니다.",
        "path_config":    "언어와 변환 설정이 저장됩니다.",

        "about_tagline":  "유튜브 영상을 클릭휠 아이팟에서 볼 수 있게 바꿔 줍니다.",
        "about_made_by":  "만든 사람: {author}",
        "about_license":  "라이선스: MIT",
        "about_repo":     "소스 코드 / 버그 신고",
        "about_issues":   "버그를 만나셨나요? GitHub Issues에 남겨 주세요.",
        "about_donate_title": "후원",
        "about_donate":   "마음에 드셨다면 개발자에게 커피 한 잔, 맥주 한 잔 어떠세요?",
        "about_donate_button": "커피 한 잔 사주기",
        "about_repo_button":   "GitHub 열기",
        "about_issues_button": "버그 신고하기",
        "about_license_full":  "라이선스 전문",
        "about_thirdparty":    "이 프로그램은 yt-dlp와 ffmpeg를 사용합니다. "
                               "각각의 라이선스는 해당 프로젝트를 따릅니다.",

        "ffmpeg_title":   "ffmpeg 가 필요합니다",
        "ffmpeg_intro":
            "영상을 변환하려면 ffmpeg 가 필요합니다. 아직 이 컴퓨터에서 찾을 수 "
            "없습니다.",
        "ffmpeg_manual":  "패키지 관리자로 설치 (권장)",
        "ffmpeg_manual_hint":
            "아래 명령으로 설치한 뒤 이 프로그램을 다시 실행하면 됩니다.",
        "ffmpeg_auto":    "직접 내려받기",
        "ffmpeg_auto_hint":
            "{credit} 에서 배포하는 정적 빌드를 받아 {path} 에 저장합니다. "
            "이 프로그램에는 ffmpeg 가 포함되어 있지 않으며, 내려받기는 사용자의 "
            "선택으로 이루어집니다.",
        "ffmpeg_license_notice":
            "ffmpeg 는 GPL 라이선스로 배포됩니다. 자세한 내용과 소스 코드는 "
            "ffmpeg.org 및 배포처에서 확인할 수 있습니다.",
        "ffmpeg_download":     "지금 내려받기",
        "ffmpeg_open_source":  "배포처 열기",
        "ffmpeg_downloading":  "내려받는 중... {percent}%",
        "ffmpeg_extracting":   "압축을 푸는 중...",
        "ffmpeg_done":         "ffmpeg 준비가 끝났습니다.",
        "ffmpeg_error":        "내려받기에 실패했습니다: {error}",
        "ffmpeg_unavailable":
            "이 환경에서는 자동 내려받기를 지원하지 않습니다. "
            "위 명령으로 직접 설치해 주세요.",
        "ffmpeg_later":        "나중에",
        "ffmpeg_missing_run":
            "ffmpeg 를 찾을 수 없어 변환을 시작할 수 없습니다. "
            "설정 창을 열어 설치를 진행해 주세요.",
    },
    "en": {
        "language_name":  "English",
        "queue":          "Queue",
        "single_video":   "Single video",
        "playlist":       "Playlist",
        "device":         "Device:",
        "video_quality":  "Video:",
        "audio_quality":  "Audio:",
        "url_hint":       "YouTube URL",
        "add":            "Add",
        "remove":         "Remove selected",
        "clear":          "Clear",
        "start":          "Download && Convert",
        "convert_only":   "Convert existing files",
        "stop":           "Stop",
        "settings":       "Settings",
        "help":           "?",
        "show_log":       "Show log",
        "hide_log":       "Hide log",
        "ready":          "Ready",
        "stopped":        "Stopped",
        "downloading":    "Downloading",
        "converting":     "Converting",
        "file_counter":   "File {current}/{total}",
        "eta_calc":       "Estimating...",
        "eta_left":       "about {time} left",
        "output_path":    "Output: {path}",
        "no_url":         "Add a URL first.",
        "no_files":       "No files to convert.",
        "no_new_files":   "No new files to convert.",
        "closing":        "A task is running. Quit anyway?",

        "device_5g":      "5th gen (2005)",
        "device_5.5g":    "5.5th gen (2006)",
        "device_classic": "6th / 7th gen classic",
        "device_5g_tip":
            "iPod with Video. Plays up to 320x240 at 768 kbps.",
        "device_5.5g_tip":
            "The brighter late model. Plays up to 640x480 at 1.5 Mbps.",
        "device_classic_tip":
            "iPod classic 80/120/160GB. Plays up to 640x480 at 2.5 Mbps.",

        "quality_low":    "Low ({kbps}k)",
        "quality_medium": "Medium ({kbps}k)",
        "quality_high":   "High ({kbps}k)",

        "language":       "Language:",
        "settings_title": "Settings",
        "tab_general":    "General",
        "tab_encoding":   "Conversion",
        "tab_cleanup":    "Cleanup",
        "tab_paths":      "Folders",
        "tab_about":      "About",
        "paths":          "Folder locations",
        "converted":      "Converted",
        "skipped":        "Skipped",
        "failed":         "Failed",
        "aborted":        "Aborted",
        "minutes":        "{n} min",
        "seconds":        "{n} sec",
        "hours":          "{h} h {m} min",
        "done_title":     f"{APP_NAME} — Finished",
        "done_stopped":   f"{APP_NAME} — Stopped",
        "summary":        "Converted {converted} · Skipped {skipped} · Failed {failed}",
        "summary_abort":  "Converted {converted} · Skipped {skipped} · Failed {failed} · Aborted {aborted}",
        "open_folder":    "Open output folder",
        "help_title":     f"{APP_NAME} Guide",
        "close":          "Close",

        "aspect":            "Aspect:",
        "aspect_letterbox":  "Fill the screen (black bars)",
        "aspect_preserve":   "Keep original shape",
        "aspect_hint":
            "The iPod screen is 4:3. Filling adds black bars to match it, while "
            "keeping the original shape leaves the picture as it is. Either way "
            "it looks much the same on the device, but keeping the shape makes "
            "slightly smaller files.",

        "codec":          "Video codec:",
        "codec_h264":     "H.264 (recommended)",
        "codec_mpeg4":    "MPEG-4 (compatibility)",
        "codec_hint":
            "H.264 gives better quality at the same size and suits almost every "
            "case. If a file refuses to play, try MPEG-4 instead.",

        "cleanup_folder":  "Folder:",
        "cleanup_delete_selected": "Delete selected",
        "cleanup_delete_all":      "Delete all",
        "cleanup_refresh": "Refresh",
        "cleanup_empty":   "This folder is empty.",
        "cleanup_total":   "{count} files · {size}",
        "cleanup_confirm_selected":
            "Delete {count} selected file(s) ({size}).\nThis cannot be undone. Continue?",
        "cleanup_confirm_all":
            "Delete all {count} file(s) ({size}) in {folder}.\nThis cannot be undone. Continue?",
        "cleanup_done":    "Deleted {count} file(s).",
        "cleanup_failed":  "Could not delete {count} file(s).",
        "cleanup_nothing_selected": "Select the files you want to delete.",
        "cleanup_title":   "Clean up files",
        "cleanup_button":  "Clean up",
        "record_title":    "Download history",
        "record_hint":
            "A list of videos already downloaded, used to avoid fetching the same "
            "one twice. Deleting the files doesn't clear this list — reset it here "
            "if you want to download them again.",
        "record_count":    "{count} video(s) recorded",
        "record_empty":    "No history yet.",
        "record_reset":    "Reset history",
        "record_confirm":
            "Clear {count} download record(s).\n"
            "You'll be able to download those videos again. Continue?",
        "record_done":     "History cleared.",

        "folder_tempv":     "tempv — single video originals",
        "folder_playlistv": "playlistv — playlist originals",
        "folder_changedv":  "changedv — converted videos",
        "folder_archivev":  "archivev — originals kept after conversion",

        "path_tempv":     "Originals downloaded as single videos are stored here.",
        "path_playlistv": "Originals downloaded from playlists are stored here.",
        "path_changedv":  "Converted videos land here. These are the files for your iPod.",
        "path_archivev":  "Originals move here once conversion succeeds.",
        "path_bin":       "ffmpeg downloaded through this program is stored here.",
        "path_archive_file": "A list of videos already downloaded, so the same one isn't fetched twice.",
        "path_config":    "Your language and conversion settings are stored here.",

        "about_tagline":  "Turns YouTube videos into something a click-wheel iPod can play.",
        "about_made_by":  "Made by {author}",
        "about_license":  "License: MIT",
        "about_repo":     "Source code / bug reports",
        "about_issues":   "Run into a bug? Please open an issue on GitHub.",
        "about_donate_title": "Support",
        "about_donate":   "If you like it, how about a coffee or a beer for the developer?",
        "about_donate_button": "Buy me a coffee",
        "about_repo_button":   "Open GitHub",
        "about_issues_button": "Report a bug",
        "about_license_full":  "Full license text",
        "about_thirdparty":    "This program uses yt-dlp and ffmpeg. Each is covered "
                               "by its own license.",

        "ffmpeg_title":   "ffmpeg is required",
        "ffmpeg_intro":
            "Converting video requires ffmpeg, which wasn't found on this computer.",
        "ffmpeg_manual":  "Install with a package manager (recommended)",
        "ffmpeg_manual_hint":
            "Run the command below, then start this program again.",
        "ffmpeg_auto":    "Download it here",
        "ffmpeg_auto_hint":
            "Fetches the static build published by {credit} and stores it in {path}. "
            "ffmpeg is not bundled with this program — the download happens only if "
            "you choose it.",
        "ffmpeg_license_notice":
            "ffmpeg is distributed under the GPL. Details and source code are "
            "available from ffmpeg.org and the build provider.",
        "ffmpeg_download":     "Download now",
        "ffmpeg_open_source":  "Open provider page",
        "ffmpeg_downloading":  "Downloading... {percent}%",
        "ffmpeg_extracting":   "Extracting...",
        "ffmpeg_done":         "ffmpeg is ready.",
        "ffmpeg_error":        "Download failed: {error}",
        "ffmpeg_unavailable":
            "Automatic download isn't available on this platform. "
            "Please install ffmpeg using the command above.",
        "ffmpeg_later":        "Later",
        "ffmpeg_missing_run":
            "ffmpeg was not found, so conversion cannot start. "
            "Open Settings to install it.",
    },
}


HELP_SECTIONS = {
    "ko": [
        ("기기",
         "가지고 있는 아이팟 세대를 고릅니다. 세대마다 재생할 수 있는 화면 크기와 "
         "비트레이트 상한이 달라, 여기서 고른 값에 맞춰 나머지 설정이 자동으로 "
         "정해집니다. 5세대는 320×240 까지, 5.5세대와 클래식은 640×480 까지 "
         "재생합니다. 어느 세대든 액정 자체는 320×240 이므로, 큰 화면 크기는 "
         "TV 출력으로 볼 때 의미가 있습니다. 잘 모르겠다면 5세대로 두면 모든 "
         "기기에서 재생됩니다."),

        ("단일 영상 / 재생목록",
         "받으려는 주소의 종류를 고릅니다. 재생목록을 고르면 주소에 묶인 영상을 "
         "전부 받고, 파일 이름 앞에 001, 002 같은 순번이 붙습니다. 단일 영상을 "
         "고르면 주소에 재생목록이 섞여 있어도 영상 하나만 받습니다."),

        ("영상 / 소리",
         "화면과 소리의 품질을 따로 고릅니다. 고른 기기가 감당할 수 있는 범위 "
         "안에서 세 단계가 주어지며, 괄호 안의 숫자가 실제 비트레이트입니다. "
         "음악 위주의 영상이라면 영상을 낮게, 소리를 높게 두는 식으로 조합하면 "
         "됩니다. 높음은 기기의 상한을 그대로 쓰기 때문에 배터리 소모와 발열이 "
         "늘어납니다."),

        ("설정",
         "언어와 변환 방식을 바꾸고, 쌓인 파일을 정리하고, 폴더 위치와 프로그램 "
         "정보를 확인할 수 있습니다. 바꾼 설정은 바로 적용되고 다음에 프로그램을 "
         "켤 때도 유지됩니다."),

        ("주소 입력칸 / 추가",
         "유튜브 주소를 붙여 넣고 추가를 누르면 아래 대기열에 쌓입니다. "
         "엔터를 눌러도 같습니다. 여러 개를 넣어두면 순서대로 처리합니다."),

        ("대기열",
         "처리할 주소 목록입니다. 위에서부터 차례로 진행합니다."),

        ("선택 삭제 / 전체 삭제",
         "선택 삭제는 대기열에서 고른 줄만 지웁니다. 전체 삭제는 목록을 비웁니다. "
         "이미 받은 파일은 지워지지 않습니다."),

        ("다운로드 후 변환",
         "대기열의 주소를 받아서 곧바로 아이팟용으로 변환합니다. 보통은 이 버튼만 "
         "쓰면 됩니다. 이미 받은 적이 있는 영상은 다시 받지 않고 넘어갑니다."),

        ("기존 파일 변환",
         "새로 받지 않고, 이미 컴퓨터에 있는 원본만 변환합니다. 변환 도중에 "
         "중지했거나 오류로 멈췄을 때 이어서 하는 용도입니다. 직접 준비한 영상 "
         "파일을 원본 폴더에 넣어두고 이 버튼으로 변환할 수도 있습니다."),

        ("중지",
         "진행 중인 작업을 멈춥니다. 만들다 만 파일은 자동으로 지워지므로 "
         "망가진 영상이 남지 않습니다. 원본은 그대로 있으니 기존 파일 변환으로 "
         "다시 이어서 하면 됩니다."),

        ("로그 보기",
         "프로그램이 내부에서 주고받는 자세한 기록을 펼칩니다. 평소에는 볼 필요가 "
         "없고, 문제가 생겼을 때 원인을 확인하는 용도입니다. 버그를 신고할 때 이 "
         "내용을 함께 보내주시면 큰 도움이 됩니다."),

        ("진행률 막대",
         "지금 처리 중인 파일 하나가 얼마나 진행됐는지 보여줍니다. 오른쪽에는 "
         "전체 몇 개 중 몇 번째인지와 남은 시간이 함께 표시됩니다. 남은 시간은 "
         "처리 속도를 바탕으로 계속 다시 계산됩니다."),

        ("저장 폴더 열기",
         "변환이 끝난 영상이 담긴 폴더를 파일 관리자로 엽니다."),

        ("ffmpeg 에 대하여",
         "영상 변환은 ffmpeg 라는 별도 프로그램이 담당합니다. 이 프로그램에는 "
         "포함되어 있지 않으므로, 컴퓨터에 없다면 처음 실행할 때 설치 방법을 "
         "안내합니다. 패키지 관리자로 직접 설치하거나, 안내 창에서 내려받기를 "
         "선택할 수 있습니다."),

        ("설정 › 변환",
         "화면 비율과 영상 코덱을 정합니다. 화면 채우기는 4:3 에 맞춰 위아래에 "
         "검은 띠를 넣고, 원본 비율 유지는 띠 없이 원본 모양을 그대로 둡니다. "
         "코덱은 H.264 가 기본이며, 재생이 안 되는 파일이 있을 때만 MPEG-4 로 "
         "바꿔 보면 됩니다."),

        ("파일 정리",
         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "
         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 삭제는 "
         "되돌릴 수 없습니다.\n\n"
         "아래쪽의 다운로드 기록은 이미 받은 영상의 목록입니다. 폴더에서 파일을 "
         "지워도 이 기록은 남아 있어서, 같은 영상을 다시 받으려 하면 건너뜁니다. "
         "다시 받고 싶다면 기록을 초기화하세요."),

        ("설정 › 정보",
         "만든 사람, 라이선스, 소스 코드 주소를 볼 수 있습니다. 버그 신고 링크와 "
         "후원 링크도 여기에 있습니다."),
    ],
    "en": [
        ("Device",
         "Pick the iPod generation you own. Each generation decodes a different "
         "maximum picture size and bitrate, and the rest of the settings follow "
         "from your choice. The 5th generation handles up to 320x240; the 5.5th "
         "and the classic handle up to 640x480. Every one of them has a 320x240 "
         "screen, so the larger sizes only matter for TV output. When in doubt, "
         "leave it on 5th generation — those files play everywhere."),

        ("Single video / Playlist",
         "Choose what kind of link you're adding. Playlist downloads every video "
         "in the link and prefixes filenames with 001, 002 and so on. Single video "
         "grabs just the one video, even if the link also points at a playlist."),

        ("Video / Audio",
         "Picture and sound quality are chosen separately, within what the selected "
         "device can handle; the number in brackets is the actual bitrate. Low "
         "video with high audio suits a music video, for instance. High uses the "
         "device's ceiling, which drains the battery faster and runs warmer."),

        ("Settings",
         "Change the language and conversion options, clear out accumulated files, "
         "and see where things are stored along with program information. Changes "
         "take effect immediately and are remembered next time."),

        ("URL box / Add",
         "Paste a YouTube link and press Add to put it in the queue below. Enter "
         "does the same. Add several and they'll be handled in order."),

        ("Queue",
         "The list of links waiting to be processed, top to bottom."),

        ("Remove selected / Clear",
         "Remove selected drops the highlighted lines from the queue. Clear empties "
         "the list. Neither deletes files you've already downloaded."),

        ("Download && Convert",
         "Fetches everything in the queue and converts it for your iPod straight "
         "away. This is the button you'll normally use. Videos you've already "
         "downloaded before are skipped."),

        ("Convert existing files",
         "Converts originals already on your computer without downloading anything "
         "new. Use it to pick up where you left off after stopping or an error. You "
         "can also drop your own video files into the source folder and convert "
         "them this way."),

        ("Stop",
         "Halts the current job. Half-finished output is deleted automatically, so "
         "you won't be left with a broken video. The original stays put — use "
         "Convert existing files to resume."),

        ("Show log",
         "Opens the detailed technical record of what the program is doing. You "
         "don't normally need it; it's there for working out what went wrong. "
         "Including it in a bug report helps a great deal."),

        ("Progress bar",
         "Shows how far along the current file is. To the right you'll see which "
         "file of how many, and the estimated time left, which is recalculated "
         "continuously from the processing speed."),

        ("Open output folder",
         "Opens the folder holding your converted videos in the file manager."),

        ("About ffmpeg",
         "The actual conversion is done by a separate program called ffmpeg, which "
         "is not bundled here. If it isn't on your computer, you'll be shown how to "
         "install it on first run — either through your package manager or by "
         "choosing to download it from the dialog."),

        ("Settings › Conversion",
         "Sets the aspect handling and the video codec. Filling the screen adds "
         "black bars to reach 4:3, while keeping the original shape leaves the "
         "picture as it is. H.264 is the default codec; switch to MPEG-4 only if "
         "a file refuses to play."),

        ("Clean up",
         "Deletes video files that have piled up. Pick a folder to see its contents "
         "and total size, then remove individual files or empty it entirely. "
         "Deletion cannot be undone.\n\n"
         "The download history below lists videos you've already fetched. Deleting "
         "the files doesn't clear it, so the same video will be skipped next time. "
         "Reset the history if you want to download it again."),

        ("Settings › About",
         "Shows the author, license and source code location. Bug report and "
         "support links live here too."),
    ],
}


CLEANUP_FOLDERS = [
    ("folder_tempv", TEMPV, VALID_EXTENSIONS),
    ("folder_playlistv", PLAYLISTV, VALID_EXTENSIONS),
    ("folder_changedv", CHANGEDV, OUTPUT_EXTENSIONS),
    ("folder_archivev", ARCHIVEV, VALID_EXTENSIONS),
]


# ============================================
# 설정 파일
# ============================================

def load_config():
    config = {
        "device": DEFAULT_DEVICE,
        "video_quality": DEFAULT_VIDEO,
        "audio_quality": DEFAULT_AUDIO,
        "codec": DEFAULT_CODEC,
        "aspect": DEFAULT_ASPECT,
        "language": DEFAULT_LANGUAGE,
    }

    if not CONFIG_FILE.exists():
        return config

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return config

    if data.get("device") in DEVICE_PROFILES:
        config["device"] = data["device"]

    for key, table in (
        ("video_quality", AUDIO_BITRATES),
        ("audio_quality", AUDIO_BITRATES),
    ):
        if data.get(key) in table:
            config[key] = data[key]
        elif data.get("quality") in table:
            config[key] = data["quality"]

    if data.get("codec") in VIDEO_CODECS:
        config["codec"] = data["codec"]

    if data.get("aspect") in ASPECT_MODES:
        config["aspect"] = data["aspect"]

    if data.get("language") in TEXTS:
        config["language"] = data["language"]

    return config


def save_config(config):
    try:
        CONFIG_FILE.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


# ============================================
# 유틸
# ============================================

def collect_files(source_dir, extensions):
    files = []

    if not source_dir.is_dir():
        return files

    for file in sorted(source_dir.iterdir()):
        if not file.is_file():
            continue
        if file.name.startswith("."):
            continue
        if file.suffix.lower() not in extensions:
            continue
        files.append(file)

    return files


def collect_source_files(source_dir):
    return collect_files(source_dir, VALID_EXTENSIONS)


def format_size(num_bytes):
    size = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024

    return f"{size:.1f} TB"


def hidden_process_kwargs():
    """윈도우에서 콘솔 창이 깜빡이지 않게 한다."""
    if not IS_WINDOWS:
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def probe_duration(path):
    """영상 길이를 초 단위로. 실패하면 None."""
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            **hidden_process_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return None

    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def open_folder(path):
    """플랫폼별 파일 관리자로 폴더 열기."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer", str(path)])
        elif IS_MACOS:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_url(url):
    QDesktopServices.openUrl(QUrl(url))


TIME_RE   = re.compile(r"time=(\d+):(\d\d):(\d\d(?:\.\d+)?)")
SPEED_RE  = re.compile(r"speed=\s*([\d.]+)x")
DL_PCT_RE = re.compile(r"\[download\]\s+([\d.]+)% of")
DL_ETA_RE = re.compile(r"ETA\s+(?:(\d+):)?(\d+):(\d\d)")


def parse_ffmpeg_time(line):
    match = TIME_RE.search(line)

    if not match:
        return None

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_ffmpeg_speed(line):
    match = SPEED_RE.search(line)
    return float(match.group(1)) if match else None


def build_ytdlp_args(url, dest_dir, is_playlist, device):
    profile = DEVICE_PROFILES[device]
    max_height = profile["source_height"]

    if is_playlist:
        template = str(dest_dir / "%(playlist_index|000)03d - %(title)s [%(id)s].%(ext)s")
    else:
        template = str(dest_dir / "%(title)s [%(id)s].%(ext)s")

    args = [
        "-f",
        f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]",
        "-o", template,
        "--no-overwrites",
        "--trim-filenames", "200",
        "--download-archive", str(ARCHIVE_FILE),
        "--newline",
    ]

    # yt-dlp 는 영상과 소리를 따로 받아 ffmpeg 로 합친다. PATH 에 ffmpeg 가 없고
    # 직접 내려받은 것을 쓰는 경우, 그 위치를 알려 주지 않으면 병합이 되지 않는다.
    if os.path.sep in FFMPEG:
        args += ["--ffmpeg-location", str(Path(FFMPEG).parent)]

    if is_playlist:
        args += ["--yes-playlist", "--ignore-errors"]
    else:
        args += ["--no-playlist"]

    args.append(url)
    return args


def build_scale_filter(width, height, aspect):
    """화면 크기에 맞추는 필터. 홀수 크기는 인코더가 거부하므로 짝수로 맞춘다."""
    fit = (
        f"scale=w={width}:h={height}"
        ":force_original_aspect_ratio=decrease:force_divisible_by=2"
    )

    if aspect == "preserve":
        return fit

    return f"{fit},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"


def build_ffmpeg_args(source, dest, settings):
    profile = DEVICE_PROFILES[settings["device"]]

    width  = profile["width"]
    height = profile["height"]
    video_kbps = profile["video_bitrates"][settings["video_quality"]]
    audio_kbps = AUDIO_BITRATES[settings["audio_quality"]]

    # VBV 버퍼는 보통 비트레이트의 두 배를 준다
    maxrate = video_kbps
    bufsize = video_kbps * 2

    args = [
        "-y",
        "-i", str(source),
        "-vf", build_scale_filter(width, height, settings["aspect"]),
    ]

    if settings["codec"] == "mpeg4":
        # MPEG-4 Simple Profile. 구형 기기 호환용 선택지다.
        args += [
            "-c:v", "mpeg4",
            "-profile:v", "0",
            "-vtag", "mp4v",
        ]
    else:
        args += [
            "-c:v", "libx264",
            "-profile:v", "baseline",
            "-level", profile["level"],
        ]

    args += [
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", f"{video_kbps}k",
        "-maxrate", f"{maxrate}k",
        "-bufsize", f"{bufsize}k",
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        # .part 확장자로는 컨테이너를 추론할 수 없으므로 포맷을 명시
        "-f", "mp4",
        str(dest),
    ]

    return args


# ============================================
# ffmpeg 내려받기
# ============================================

class FFmpegDownloader(QObject):
    """별도 스레드에서 ffmpeg 정적 빌드를 받아 BIN_DIR 에 넣는다."""

    progress = Signal(int)
    extracting = Signal()
    finished = Signal(bool, str)

    WANTED = ("ffmpeg", "ffprobe")

    def __init__(self, source):
        super().__init__()
        self.source = source

    def run(self):
        urls = [self.source["url"]] + list(self.source.get("extra_urls", []))

        try:
            with tempfile.TemporaryDirectory() as workdir:
                work = Path(workdir)
                archives = []

                for index, url in enumerate(urls):
                    target = work / f"download-{index}"
                    self._fetch(url, target, index, len(urls))
                    archives.append(target)

                self.extracting.emit()

                extracted = work / "extracted"
                extracted.mkdir()

                for archive in archives:
                    self._extract(archive, extracted)

                found = self._collect(extracted)

                if not found:
                    self.finished.emit(False, "ffmpeg not found in archive")
                    return

                for name, path in found.items():
                    dest = BIN_DIR / tool_filename(name)
                    shutil.copy2(path, dest)

                    if not IS_WINDOWS:
                        dest.chmod(0o755)

        except Exception as e:  # 네트워크·압축 등 어떤 실패든 사용자에게 알린다
            self.finished.emit(False, str(e))
            return

        self.finished.emit(True, "")

    def _fetch(self, url, target, index, total):
        request = urllib.request.Request(
            url, headers={"User-Agent": f"{APP_NAME}/{VERSION}"}
        )

        # macOS 의 파이썬은 시스템 인증서를 쓰지 않아 HTTPS 검증이 실패한다.
        # certifi 가 있으면 그 인증서 묶음을 쓴다.
        context = None

        try:
            import certifi
            import ssl

            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass

        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            length = response.getheader("Content-Length")
            length = int(length) if length and length.isdigit() else 0
            read = 0

            with open(target, "wb") as out:
                while True:
                    chunk = response.read(65536)

                    if not chunk:
                        break

                    out.write(chunk)
                    read += len(chunk)

                    if length:
                        base = index / total * 100
                        self.progress.emit(int(base + read / length * 100 / total))

    def _extract(self, archive, destination):
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(destination)
            return

        with tarfile.open(archive) as tf:
            tf.extractall(destination)

    def _collect(self, root):
        found = {}

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            stem = path.stem.lower()

            if stem in self.WANTED and stem not in found:
                found[stem] = path

        return found


class FFmpegSetupDialog(QDialog):
    """ffmpeg 설치 안내 창."""

    def __init__(self, parent, texts):
        super().__init__(parent)
        self.texts = texts
        self.thread = None
        self.worker = None

        self.setWindowTitle(texts["ffmpeg_title"])
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(texts["ffmpeg_intro"])
        intro.setWordWrap(True)
        layout.addWidget(intro)

        manual_box = QGroupBox(texts["ffmpeg_manual"])
        manual_layout = QVBoxLayout(manual_box)

        hint = QLabel(texts["ffmpeg_manual_hint"])
        hint.setWordWrap(True)
        manual_layout.addWidget(hint)

        command_text = package_manager_hint()
        command = QPlainTextEdit(command_text)
        command.setReadOnly(True)
        command.setFont(QFont("monospace", 9))
        command.setFixedHeight(30 + 16 * command_text.count("\n"))
        manual_layout.addWidget(command)

        layout.addWidget(manual_box)

        self.source = ffmpeg_source()

        auto_box = QGroupBox(texts["ffmpeg_auto"])
        auto_layout = QVBoxLayout(auto_box)

        if self.source:
            auto_hint = QLabel(
                texts["ffmpeg_auto_hint"].format(
                    credit=self.source["credit"], path=BIN_DIR
                )
            )
        else:
            auto_hint = QLabel(texts["ffmpeg_unavailable"])

        auto_hint.setWordWrap(True)
        auto_layout.addWidget(auto_hint)

        notice = QLabel(texts["ffmpeg_license_notice"])
        notice.setWordWrap(True)
        notice.setStyleSheet("color: gray;")
        auto_layout.addWidget(notice)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        auto_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        auto_layout.addWidget(self.status_label)

        button_row = QHBoxLayout()

        self.download_button = QPushButton(texts["ffmpeg_download"])
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setEnabled(bool(self.source))
        button_row.addWidget(self.download_button)

        if self.source:
            provider_button = QPushButton(texts["ffmpeg_open_source"])
            provider_button.clicked.connect(lambda: open_url(self.source["home"]))
            button_row.addWidget(provider_button)

        button_row.addStretch()
        auto_layout.addLayout(button_row)

        layout.addWidget(auto_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(texts["ffmpeg_later"])
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.close_button = buttons.button(QDialogButtonBox.Close)

    def start_download(self):
        if not self.source:
            return

        self.download_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(
            self.texts["ffmpeg_downloading"].format(percent=0)
        )

        self.thread = QThread(self)
        self.worker = FFmpegDownloader(self.source)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.extracting.connect(self.on_extracting)
        self.worker.finished.connect(self.on_finished)

        self.thread.start()

    def on_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.status_label.setText(
            self.texts["ffmpeg_downloading"].format(percent=percent)
        )

    def on_extracting(self):
        self.progress_bar.setValue(100)
        self.status_label.setText(self.texts["ffmpeg_extracting"])

    def on_finished(self, ok, error):
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None

        self.close_button.setEnabled(True)

        if ok:
            refresh_tools()
            self.progress_bar.setVisible(False)
            self.status_label.setText(self.texts["ffmpeg_done"])
            self.accept()
            return

        self.progress_bar.setVisible(False)
        self.status_label.setText(self.texts["ffmpeg_error"].format(error=error))
        self.download_button.setEnabled(True)


# ============================================
# 도움말 창
# ============================================

class HelpDialog(QDialog):

    def __init__(self, parent, language):
        super().__init__(parent)

        texts = TEXTS[language]
        self.setWindowTitle(texts["help_title"])
        self.resize(600, 560)

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(14)

        for title, body in HELP_SECTIONS[language]:
            title_label = QLabel(title)
            font = title_label.font()
            font.setBold(True)
            title_label.setFont(font)
            content_layout.addWidget(title_label)

            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            content_layout.addWidget(body_label)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(texts["close"])
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ============================================
# 라이선스 전문 창
# ============================================

class LicenseDialog(QDialog):

    def __init__(self, parent, texts):
        super().__init__(parent)

        self.setWindowTitle(texts["about_license_full"])
        self.resize(620, 460)

        layout = QVBoxLayout(self)

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("monospace", 9))
        view.setPlainText(MIT_LICENSE)
        layout.addWidget(view)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(texts["close"])
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ============================================
# 정보 탭
# ============================================

class AboutTab(QWidget):

    def __init__(self, parent, texts):
        super().__init__(parent)
        self.texts = texts

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(f"{APP_NAME} {VERSION} ({CODENAME})")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        tagline = QLabel(texts["about_tagline"])
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        layout.addSpacing(6)

        author = QLabel(texts["about_made_by"].format(author=AUTHOR))
        author.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(author)

        copyright_label = QLabel(COPYRIGHT)
        copyright_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(copyright_label)

        license_row = QHBoxLayout()
        license_row.addWidget(QLabel(texts["about_license"]))
        license_button = QPushButton(texts["about_license_full"])
        license_button.clicked.connect(self.show_license)
        license_row.addWidget(license_button)
        license_row.addStretch()
        layout.addLayout(license_row)

        thirdparty = QLabel(texts["about_thirdparty"])
        thirdparty.setWordWrap(True)
        thirdparty.setStyleSheet("color: gray;")
        layout.addWidget(thirdparty)

        layout.addSpacing(10)

        repo_box = QGroupBox(texts["about_repo"])
        repo_layout = QVBoxLayout(repo_box)

        issues = QLabel(texts["about_issues"])
        issues.setWordWrap(True)
        repo_layout.addWidget(issues)

        repo_row = QHBoxLayout()
        repo_button = QPushButton(texts["about_repo_button"])
        repo_button.clicked.connect(lambda: open_url(REPO_URL))
        issues_button = QPushButton(texts["about_issues_button"])
        issues_button.clicked.connect(lambda: open_url(ISSUES_URL))
        repo_row.addWidget(repo_button)
        repo_row.addWidget(issues_button)
        repo_row.addStretch()
        repo_layout.addLayout(repo_row)

        layout.addWidget(repo_box)

        donate_box = QGroupBox(texts["about_donate_title"])
        donate_layout = QVBoxLayout(donate_box)

        donate = QLabel(texts["about_donate"])
        donate.setWordWrap(True)
        donate_layout.addWidget(donate)

        donate_row = QHBoxLayout()
        donate_button = QPushButton(texts["about_donate_button"])
        donate_button.clicked.connect(lambda: open_url(DONATE_URL))
        donate_row.addWidget(donate_button)
        donate_row.addStretch()
        donate_layout.addLayout(donate_row)

        layout.addWidget(donate_box)
        layout.addStretch()

    def show_license(self):
        LicenseDialog(self, self.texts).exec()


# ============================================
# 정리 탭
# ============================================

class CleanupTab(QWidget):

    def __init__(self, parent, texts):
        super().__init__(parent)
        self.texts = texts

        layout = QVBoxLayout(self)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(texts["cleanup_folder"]))

        self.folder_combo = QComboBox()
        for key, path, extensions in CLEANUP_FOLDERS:
            self.folder_combo.addItem(texts[key], (str(path), tuple(extensions)))
        self.folder_combo.currentIndexChanged.connect(self.reload)
        folder_row.addWidget(self.folder_combo, stretch=1)

        self.refresh_button = QPushButton(texts["cleanup_refresh"])
        self.refresh_button.clicked.connect(self.reload)
        folder_row.addWidget(self.refresh_button)

        layout.addLayout(folder_row)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.file_list, stretch=1)

        self.total_label = QLabel("")
        layout.addWidget(self.total_label)

        button_row = QHBoxLayout()
        self.delete_selected_button = QPushButton(texts["cleanup_delete_selected"])
        self.delete_selected_button.clicked.connect(self.delete_selected)
        self.delete_all_button = QPushButton(texts["cleanup_delete_all"])
        self.delete_all_button.clicked.connect(self.delete_all)
        button_row.addWidget(self.delete_selected_button)
        button_row.addWidget(self.delete_all_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        # --- 다운로드 기록 ---
        record_box = QGroupBox(texts["record_title"])
        record_layout = QVBoxLayout(record_box)

        record_hint = QLabel(texts["record_hint"])
        record_hint.setWordWrap(True)
        record_hint.setStyleSheet("color: gray;")
        record_layout.addWidget(record_hint)

        record_row = QHBoxLayout()
        self.record_label = QLabel("")
        record_row.addWidget(self.record_label, stretch=1)

        self.record_button = QPushButton(texts["record_reset"])
        self.record_button.clicked.connect(self.reset_record)
        record_row.addWidget(self.record_button)

        record_layout.addLayout(record_row)
        layout.addWidget(record_box)

        self.reload()
        self.reload_record()

    def current_folder(self):
        path, extensions = self.folder_combo.currentData()
        return Path(path), list(extensions)

    def reload(self):
        folder, extensions = self.current_folder()
        self.file_list.clear()

        files = collect_files(folder, extensions)
        total = 0

        for file in files:
            try:
                size = file.stat().st_size
            except OSError:
                size = 0

            total += size

            item = QListWidgetItem(f"{file.name}   ({format_size(size)})")
            item.setData(Qt.UserRole, str(file))
            self.file_list.addItem(item)

        if files:
            self.total_label.setText(
                self.texts["cleanup_total"].format(
                    count=len(files), size=format_size(total)
                )
            )
        else:
            self.total_label.setText(self.texts["cleanup_empty"])

        has_files = bool(files)
        self.delete_selected_button.setEnabled(has_files)
        self.delete_all_button.setEnabled(has_files)

    def selected_paths(self):
        return [
            Path(item.data(Qt.UserRole))
            for item in self.file_list.selectedItems()
        ]

    def all_paths(self):
        return [
            Path(self.file_list.item(i).data(Qt.UserRole))
            for i in range(self.file_list.count())
        ]

    def total_size(self, paths):
        total = 0

        for path in paths:
            try:
                total += path.stat().st_size
            except OSError:
                pass

        return total

    def delete_paths(self, paths):
        deleted = 0
        failed = 0

        for path in paths:
            try:
                path.unlink()
                deleted += 1
            except OSError:
                failed += 1

        self.reload()

        if failed:
            QMessageBox.warning(
                self, APP_NAME, self.texts["cleanup_failed"].format(count=failed)
            )
        else:
            QMessageBox.information(
                self, APP_NAME, self.texts["cleanup_done"].format(count=deleted)
            )

    def delete_selected(self):
        paths = self.selected_paths()

        if not paths:
            QMessageBox.information(
                self, APP_NAME, self.texts["cleanup_nothing_selected"]
            )
            return

        answer = QMessageBox.question(
            self,
            APP_NAME,
            self.texts["cleanup_confirm_selected"].format(
                count=len(paths), size=format_size(self.total_size(paths))
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            self.delete_paths(paths)

    def record_entries(self):
        if not ARCHIVE_FILE.exists():
            return 0

        try:
            lines = ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0

        return len([line for line in lines if line.strip()])

    def reload_record(self):
        count = self.record_entries()

        if count:
            self.record_label.setText(
                self.texts["record_count"].format(count=count)
            )
        else:
            self.record_label.setText(self.texts["record_empty"])

        self.record_button.setEnabled(bool(count))

    def reset_record(self):
        count = self.record_entries()

        if not count:
            return

        answer = QMessageBox.question(
            self,
            APP_NAME,
            self.texts["record_confirm"].format(count=count),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            ARCHIVE_FILE.unlink(missing_ok=True)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return

        self.reload_record()
        QMessageBox.information(self, APP_NAME, self.texts["record_done"])

    def delete_all(self):
        paths = self.all_paths()

        if not paths:
            return

        folder, _ = self.current_folder()

        answer = QMessageBox.question(
            self,
            APP_NAME,
            self.texts["cleanup_confirm_all"].format(
                count=len(paths),
                size=format_size(self.total_size(paths)),
                folder=folder.name,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            self.delete_paths(paths)


# ============================================
# 정리 창
# ============================================

class CleanupDialog(QDialog):
    """설정 창을 거치지 않고 바로 여는 파일 정리 창."""

    def __init__(self, parent, texts):
        super().__init__(parent)

        self.setWindowTitle(texts["cleanup_title"])
        self.resize(560, 560)

        layout = QVBoxLayout(self)
        layout.addWidget(CleanupTab(self, texts))

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(texts["close"])
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ============================================
# 설정 창
# ============================================

class SettingsDialog(QDialog):

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = dict(config)

        texts = TEXTS[self.config["language"]]
        self.texts = texts
        self.setWindowTitle(texts["settings_title"])
        self.resize(600, 540)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # --- 일반 ---
        general = QWidget()
        general_layout = QVBoxLayout(general)
        form = QFormLayout()

        self.language_combo = QComboBox()
        for code, table in TEXTS.items():
            self.language_combo.addItem(table["language_name"], code)

        index = self.language_combo.findData(self.config["language"])
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        form.addRow(texts["language"], self.language_combo)
        general_layout.addLayout(form)

        ffmpeg_box = QGroupBox("ffmpeg")
        ffmpeg_layout = QVBoxLayout(ffmpeg_box)

        self.ffmpeg_status = QLabel("")
        self.ffmpeg_status.setWordWrap(True)
        ffmpeg_layout.addWidget(self.ffmpeg_status)

        self.ffmpeg_button = QPushButton(texts["ffmpeg_title"])
        self.ffmpeg_button.clicked.connect(self.open_ffmpeg_setup)
        ffmpeg_layout.addWidget(self.ffmpeg_button)

        general_layout.addWidget(ffmpeg_box)
        general_layout.addStretch()
        tabs.addTab(general, texts["tab_general"])

        self.update_ffmpeg_status()

        # --- 변환 ---
        encoding = QWidget()
        encoding_layout = QVBoxLayout(encoding)

        aspect_box = QGroupBox(texts["aspect"])
        aspect_layout = QVBoxLayout(aspect_box)

        self.aspect_combo = QComboBox()
        for mode in ASPECT_MODES:
            self.aspect_combo.addItem(texts[f"aspect_{mode}"], mode)

        index = self.aspect_combo.findData(self.config["aspect"])
        if index >= 0:
            self.aspect_combo.setCurrentIndex(index)

        aspect_layout.addWidget(self.aspect_combo)

        aspect_hint = QLabel(texts["aspect_hint"])
        aspect_hint.setWordWrap(True)
        aspect_hint.setStyleSheet("color: gray;")
        aspect_layout.addWidget(aspect_hint)

        encoding_layout.addWidget(aspect_box)

        codec_box = QGroupBox(texts["codec"])
        codec_layout = QVBoxLayout(codec_box)

        self.codec_combo = QComboBox()
        for codec in VIDEO_CODECS:
            self.codec_combo.addItem(texts[f"codec_{codec}"], codec)

        index = self.codec_combo.findData(self.config["codec"])
        if index >= 0:
            self.codec_combo.setCurrentIndex(index)

        codec_layout.addWidget(self.codec_combo)

        codec_hint = QLabel(texts["codec_hint"])
        codec_hint.setWordWrap(True)
        codec_hint.setStyleSheet("color: gray;")
        codec_layout.addWidget(codec_hint)

        encoding_layout.addWidget(codec_box)
        encoding_layout.addStretch()
        tabs.addTab(encoding, texts["tab_encoding"])

        # --- 폴더 위치 ---
        paths = QWidget()
        paths_outer = QVBoxLayout(paths)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        paths_layout = QVBoxLayout(content)
        paths_layout.setSpacing(10)

        entries = (
            ("tempv", TEMPV, "path_tempv"),
            ("playlistv", PLAYLISTV, "path_playlistv"),
            ("changedv", CHANGEDV, "path_changedv"),
            ("archivev", ARCHIVEV, "path_archivev"),
            ("bin", BIN_DIR, "path_bin"),
            ("download_archive.txt", ARCHIVE_FILE, "path_archive_file"),
            ("config.json", CONFIG_FILE, "path_config"),
        )

        for name, path, description_key in entries:
            description = QLabel(f"{name} — {texts[description_key]}")
            description.setWordWrap(True)
            paths_layout.addWidget(description)

            path_label = QLabel(str(path))
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            path_font = path_label.font()
            path_font.setPointSize(max(7, path_font.pointSize() - 1))
            path_label.setFont(path_font)
            path_label.setStyleSheet("color: gray;")
            paths_layout.addWidget(path_label)

        paths_layout.addStretch()
        scroll.setWidget(content)
        paths_outer.addWidget(scroll)
        tabs.addTab(paths, texts["tab_paths"])

        # --- 정보 ---
        about_scroll = QScrollArea()
        about_scroll.setWidgetResizable(True)
        about_scroll.setWidget(AboutTab(self, texts))
        tabs.addTab(about_scroll, texts["tab_about"])

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_ffmpeg_status(self):
        if ffmpeg_ready():
            self.ffmpeg_status.setText(f"{FFMPEG}")
            self.ffmpeg_status.setStyleSheet("color: gray;")
            self.ffmpeg_button.setVisible(False)
        else:
            self.ffmpeg_status.setText(self.texts["ffmpeg_intro"])
            self.ffmpeg_status.setStyleSheet("")
            self.ffmpeg_button.setVisible(True)

    def open_ffmpeg_setup(self):
        FFmpegSetupDialog(self, self.texts).exec()
        self.update_ffmpeg_status()

    def result_config(self):
        return {
            "language": self.language_combo.currentData(),
            "aspect": self.aspect_combo.currentData(),
            "codec": self.codec_combo.currentData(),
        }


# ============================================
# 메인 창
# ============================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.config = load_config()

        self.proc = None
        self.stage = None
        self.stopping = False

        self.download_queue = []
        self.convert_queue = []
        self.total_files = 0
        self.current_index = 0

        self.current_source = None
        self.current_temp = None
        self.current_output = None
        self.current_duration = None
        self.speed_samples = deque(maxlen=8)

        self.stats = {"converted": 0, "skipped": 0, "failed": 0}
        self.collapsed_height = COLLAPSED_HEIGHT

        self._build_ui()
        self._build_tray()
        self.retranslate()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        self.queue_box = QGroupBox()
        queue_layout = QVBoxLayout(self.queue_box)

        # --- 기기 선택 ---
        device_row = QHBoxLayout()
        self.device_label = QLabel()
        device_row.addWidget(self.device_label)

        self.device_combo = QComboBox()
        for key in DEVICE_PROFILES:
            self.device_combo.addItem("", key)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_row.addWidget(self.device_combo)

        self.device_tip = QLabel("")
        self.device_tip.setStyleSheet("color: gray;")
        device_row.addWidget(self.device_tip, stretch=1)

        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_settings)
        device_row.addWidget(self.settings_button)

        queue_layout.addLayout(device_row)

        # --- 모드와 품질 ---
        mode_row = QHBoxLayout()
        self.radio_video = QRadioButton()
        self.radio_playlist = QRadioButton()
        self.radio_video.setChecked(True)
        mode_row.addWidget(self.radio_video)
        mode_row.addWidget(self.radio_playlist)
        mode_row.addStretch()

        self.video_label = QLabel()
        mode_row.addWidget(self.video_label)

        self.video_combo = QComboBox()
        for key in AUDIO_BITRATES:
            self.video_combo.addItem("", key)
        self.video_combo.currentIndexChanged.connect(self._on_quality_changed)
        mode_row.addWidget(self.video_combo)

        self.audio_label = QLabel()
        mode_row.addWidget(self.audio_label)

        self.audio_combo = QComboBox()
        for key in AUDIO_BITRATES:
            self.audio_combo.addItem("", key)
        self.audio_combo.currentIndexChanged.connect(self._on_quality_changed)
        mode_row.addWidget(self.audio_combo)

        queue_layout.addLayout(mode_row)

        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.returnPressed.connect(self.add_url)
        self.add_button = QPushButton()
        self.add_button.clicked.connect(self.add_url)
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self.add_button)
        queue_layout.addLayout(url_row)

        self.url_list = QListWidget()
        self.url_list.setMaximumHeight(110)
        queue_layout.addWidget(self.url_list)

        list_row = QHBoxLayout()
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self.url_list.clear)
        list_row.addWidget(self.remove_button)
        list_row.addWidget(self.clear_button)
        list_row.addStretch()
        queue_layout.addLayout(list_row)

        layout.addWidget(self.queue_box)

        action_row = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_download)
        self.convert_button = QPushButton()
        self.convert_button.clicked.connect(self.start_convert_only)
        self.stop_button = QPushButton()
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)

        self.log_button = QPushButton()
        self.log_button.setCheckable(True)
        self.log_button.setChecked(False)
        self.log_button.clicked.connect(self.toggle_log)

        action_row.addWidget(self.start_button)
        action_row.addWidget(self.convert_button)
        action_row.addWidget(self.stop_button)
        action_row.addWidget(self.log_button)
        layout.addLayout(action_row)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, stretch=1)

        self.percent_label = QLabel("0%")
        self.percent_label.setMinimumWidth(45)
        progress_row.addWidget(self.percent_label)

        self.counter_label = QLabel("")
        self.counter_label.setMinimumWidth(90)
        progress_row.addWidget(self.counter_label)

        self.eta_label = QLabel("")
        self.eta_label.setMinimumWidth(130)
        progress_row.addWidget(self.eta_label)

        layout.addLayout(progress_row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setFont(QFont("monospace", 9))
        self.log_view.setMinimumHeight(0)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view, stretch=1)

        bottom_row = QHBoxLayout()
        self.help_button = QPushButton()
        self.help_button.setMaximumWidth(36)
        self.help_button.clicked.connect(self.open_help)
        bottom_row.addWidget(self.help_button)

        self.output_label = QLabel()
        bottom_row.addWidget(self.output_label, stretch=1)

        self.cleanup_button = QPushButton()
        self.cleanup_button.clicked.connect(self.open_cleanup)
        bottom_row.addWidget(self.cleanup_button)

        self.folder_button = QPushButton()
        self.folder_button.clicked.connect(lambda: open_folder(CHANGEDV))
        bottom_row.addWidget(self.folder_button)

        layout.addLayout(bottom_row)

        self.setCentralWidget(central)
        self.resize(900, COLLAPSED_HEIGHT)

    def _build_tray(self):
        self.tray = None

        icon_path = bundle_dir() / "assets" / "konvin.png"

        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = self.style().standardIcon(QStyle.SP_MediaPlay)

        self.setWindowIcon(icon)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"{APP_NAME} {VERSION}")
        self.tray.show()

    # --------------------------------------------
    # 첫 실행 점검
    # --------------------------------------------

    def check_ffmpeg(self):
        if ffmpeg_ready():
            return

        FFmpegSetupDialog(self, TEXTS[self.config["language"]]).exec()

    # --------------------------------------------
    # 언어 적용
    # --------------------------------------------

    def tr_(self, key, **kwargs):
        text = TEXTS[self.config["language"]].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def retranslate(self):
        self.setWindowTitle(f"{APP_NAME} {VERSION} ({CODENAME})")

        self.queue_box.setTitle(self.tr_("queue"))
        self.device_label.setText(self.tr_("device"))
        self.radio_video.setText(self.tr_("single_video"))
        self.radio_playlist.setText(self.tr_("playlist"))
        self.video_label.setText(self.tr_("video_quality"))
        self.audio_label.setText(self.tr_("audio_quality"))
        self.settings_button.setText(self.tr_("settings"))
        self.help_button.setText(self.tr_("help"))
        self.url_edit.setPlaceholderText(self.tr_("url_hint"))
        self.add_button.setText(self.tr_("add"))
        self.remove_button.setText(self.tr_("remove"))
        self.clear_button.setText(self.tr_("clear"))
        self.start_button.setText(self.tr_("start"))
        self.convert_button.setText(self.tr_("convert_only"))
        self.stop_button.setText(self.tr_("stop"))
        self.cleanup_button.setText(self.tr_("cleanup_button"))
        self.folder_button.setText(self.tr_("open_folder"))
        self.output_label.setText(self.tr_("output_path", path=CHANGEDV))

        self.log_button.setText(
            self.tr_("hide_log") if self.log_view.isVisible() else self.tr_("show_log")
        )

        self.device_combo.blockSignals(True)
        for i in range(self.device_combo.count()):
            key = self.device_combo.itemData(i)
            self.device_combo.setItemText(i, self.tr_(f"device_{key}"))

        index = self.device_combo.findData(self.config["device"])
        if index >= 0:
            self.device_combo.setCurrentIndex(index)
        self.device_combo.blockSignals(False)

        self.update_quality_labels()

        if not self.proc:
            self.status_label.setText(self.tr_("ready"))

    def update_quality_labels(self):
        """기기에 따라 비트레이트 표시가 달라지므로 다시 그린다."""
        device = self.config["device"]
        profile = DEVICE_PROFILES[device]

        self.device_tip.setText(self.tr_(f"device_{device}_tip"))

        self.video_combo.blockSignals(True)
        for i in range(self.video_combo.count()):
            key = self.video_combo.itemData(i)
            self.video_combo.setItemText(
                i, self.tr_(f"quality_{key}", kbps=profile["video_bitrates"][key])
            )

        index = self.video_combo.findData(self.config["video_quality"])
        if index >= 0:
            self.video_combo.setCurrentIndex(index)
        self.video_combo.blockSignals(False)

        self.audio_combo.blockSignals(True)
        for i in range(self.audio_combo.count()):
            key = self.audio_combo.itemData(i)
            self.audio_combo.setItemText(
                i, self.tr_(f"quality_{key}", kbps=AUDIO_BITRATES[key])
            )

        index = self.audio_combo.findData(self.config["audio_quality"])
        if index >= 0:
            self.audio_combo.setCurrentIndex(index)
        self.audio_combo.blockSignals(False)

    def _on_device_changed(self):
        self.config["device"] = self.device_combo.currentData()
        save_config(self.config)
        self.update_quality_labels()

    def _on_quality_changed(self):
        self.config["video_quality"] = self.video_combo.currentData()
        self.config["audio_quality"] = self.audio_combo.currentData()
        save_config(self.config)

    def open_settings(self):
        dialog = SettingsDialog(self, self.config)

        if dialog.exec() != QDialog.Accepted:
            return

        self.config.update(dialog.result_config())
        save_config(self.config)
        self.retranslate()

    def open_help(self):
        HelpDialog(self, self.config["language"]).exec()

    def open_cleanup(self):
        CleanupDialog(self, TEXTS[self.config["language"]]).exec()

    def toggle_log(self):
        visible = self.log_button.isChecked()

        if visible:
            self.collapsed_height = self.height()
            self.log_view.setVisible(True)
            self.resize(self.width(), max(self.height(), EXPANDED_HEIGHT))
        else:
            self.log_view.setVisible(False)
            self.centralWidget().layout().activate()
            self.centralWidget().adjustSize()
            self.resize(self.width(), self.collapsed_height)

        self.log_button.setText(
            self.tr_("hide_log") if visible else self.tr_("show_log")
        )

    # --------------------------------------------
    # 로그 / 진행률 표시
    # --------------------------------------------

    def log(self, text):
        self.log_view.appendPlainText(text.rstrip())
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_progress(self, percent):
        value = int(max(0, min(100, percent)))
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")

    def set_counter(self, current, total):
        if total:
            self.counter_label.setText(
                self.tr_("file_counter", current=current, total=total)
            )
        else:
            self.counter_label.setText("")

    def format_eta(self, seconds):
        if seconds is None or seconds < 0:
            return self.tr_("eta_calc")

        seconds = int(seconds)

        if seconds < 60:
            return self.tr_("eta_left", time=self.tr_("seconds", n=seconds))

        if seconds < 3600:
            return self.tr_("eta_left", time=self.tr_("minutes", n=seconds // 60))

        return self.tr_(
            "eta_left",
            time=self.tr_("hours", h=seconds // 3600, m=(seconds % 3600) // 60),
        )

    def set_eta(self, seconds):
        self.eta_label.setText(self.format_eta(seconds))

    def reset_progress(self):
        self.set_progress(0)
        self.eta_label.setText("")
        self.counter_label.setText("")

    def set_running(self, running):
        self.start_button.setEnabled(not running)
        self.convert_button.setEnabled(not running)
        self.add_button.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.cleanup_button.setEnabled(not running)
        self.device_combo.setEnabled(not running)
        self.stop_button.setEnabled(running)

    # --------------------------------------------
    # 큐 조작
    # --------------------------------------------

    def add_url(self):
        url = self.url_edit.text().strip()

        if not url:
            return

        self.url_list.addItem(url)
        self.url_edit.clear()

    def remove_selected(self):
        for item in self.url_list.selectedItems():
            self.url_list.takeItem(self.url_list.row(item))

    def queued_urls(self):
        return [self.url_list.item(i).text() for i in range(self.url_list.count())]

    def dest_dir(self):
        return PLAYLISTV if self.radio_playlist.isChecked() else TEMPV

    # --------------------------------------------
    # 실행
    # --------------------------------------------

    def require_ffmpeg(self):
        if ffmpeg_ready():
            return True

        QMessageBox.warning(
            self, APP_NAME, self.tr_("ffmpeg_missing_run"), QMessageBox.Ok
        )

        FFmpegSetupDialog(self, TEXTS[self.config["language"]]).exec()
        return ffmpeg_ready()

    def start_download(self):
        urls = self.queued_urls()

        if not urls:
            QMessageBox.information(self, APP_NAME, self.tr_("no_url"))
            return

        if not self.require_ffmpeg():
            return

        self.stopping = False
        self.stats = {"converted": 0, "skipped": 0, "failed": 0}
        self.download_queue = list(urls)
        self.convert_queue = []
        self.total_files = len(urls)
        self.current_index = 0

        self.set_running(True)
        self.reset_progress()
        self.log("=" * 50)
        self.run_next_download()

    def start_convert_only(self):
        files = collect_source_files(TEMPV) + collect_source_files(PLAYLISTV)

        if not files:
            QMessageBox.information(self, APP_NAME, self.tr_("no_files"))
            return

        if not self.require_ffmpeg():
            return

        self.stopping = False
        self.stats = {"converted": 0, "skipped": 0, "failed": 0}
        self.download_queue = []
        self.convert_queue = files
        self.total_files = len(files)
        self.current_index = 0

        self.set_running(True)
        self.reset_progress()
        self.log("=" * 50)
        self.run_next_convert()

    def run_next_download(self):
        if self.stopping or not self.download_queue:
            self.build_convert_queue()
            return

        url = self.download_queue.pop(0)
        self.current_index += 1

        self.stage = "download"
        self.status_label.setText(f"{self.tr_('downloading')}: {url}")
        self.set_counter(self.current_index, self.total_files)
        self.set_progress(0)
        self.set_eta(None)
        self.log("")
        self.log(f"--- Downloading: {url}")

        self.start_process(
            YTDLP,
            build_ytdlp_args(
                url,
                self.dest_dir(),
                self.radio_playlist.isChecked(),
                self.config["device"],
            ),
        )

    def build_convert_queue(self):
        if self.stopping:
            self.finish()
            return

        self.convert_queue = collect_source_files(self.dest_dir())

        if not self.convert_queue:
            self.log("")
            self.log(self.tr_("no_new_files"))
            self.finish()
            return

        self.total_files = len(self.convert_queue)
        self.current_index = 0
        self.run_next_convert()

    def run_next_convert(self):
        if self.stopping or not self.convert_queue:
            self.finish()
            return

        source = self.convert_queue.pop(0)
        self.current_index += 1

        output = CHANGEDV / f"{source.stem}_iPod.m4v"

        if output.exists():
            self.log(f"Skipped (already exists): {output.name}")
            self.stats["skipped"] += 1
            self.run_next_convert()
            return

        temp_output = CHANGEDV / f".{source.stem}_iPod.m4v.part"
        temp_output.unlink(missing_ok=True)

        self.current_source = source
        self.current_temp = temp_output
        self.current_output = output
        self.current_duration = probe_duration(source)
        self.speed_samples.clear()

        settings = {
            "device": self.config["device"],
            "video_quality": self.video_combo.currentData(),
            "audio_quality": self.audio_combo.currentData(),
            "codec": self.config["codec"],
            "aspect": self.config["aspect"],
        }

        profile = DEVICE_PROFILES[settings["device"]]

        self.stage = "convert"
        self.status_label.setText(f"{self.tr_('converting')}: {source.name}")
        self.set_counter(self.current_index, self.total_files)
        self.set_progress(0)
        self.set_eta(None)
        self.log("")
        self.log(
            f"--- Converting: {source.name}  "
            f"[{settings['device']} {profile['width']}x{profile['height']} "
            f"{settings['codec']} / video {settings['video_quality']} "
            f"/ audio {settings['audio_quality']}]"
        )

        self.start_process(FFMPEG, build_ffmpeg_args(source, temp_output, settings))

    def start_process(self, program, args):
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_output)
        self.proc.finished.connect(self.on_finished)
        self.proc.errorOccurred.connect(self.on_error)
        self.proc.start(program, args)

    # --------------------------------------------
    # 출력 파싱
    # --------------------------------------------

    def on_output(self):
        if not self.proc:
            return

        text = self.proc.readAllStandardOutput().data().decode("utf-8", errors="replace")

        for line in text.replace("\r", "\n").splitlines():
            if not line.strip():
                continue

            self.log(line)

            if self.stage == "download":
                self.update_download_progress(line)
            elif self.stage == "convert":
                self.update_convert_progress(line)

    def update_download_progress(self, line):
        match = DL_PCT_RE.search(line)

        if match:
            self.set_progress(float(match.group(1)))

        eta = DL_ETA_RE.search(line)

        if eta:
            hours, minutes, seconds = eta.groups()
            total = int(minutes) * 60 + int(seconds)

            if hours:
                total += int(hours) * 3600

            self.set_eta(total)

    def update_convert_progress(self, line):
        elapsed = parse_ffmpeg_time(line)

        if elapsed is None or not self.current_duration:
            return

        self.set_progress(elapsed / self.current_duration * 100)

        speed = parse_ffmpeg_speed(line)

        if speed and speed > 0:
            self.speed_samples.append(speed)
            average = sum(self.speed_samples) / len(self.speed_samples)
            self.set_eta((self.current_duration - elapsed) / average)

    # --------------------------------------------
    # 프로세스 이벤트
    # --------------------------------------------

    def on_error(self, error):
        if error == QProcess.FailedToStart:
            name = "yt-dlp" if self.stage == "download" else "ffmpeg"
            self.log(f"{name}: failed to start")
            self.cleanup_temp()
            self.finish()

    def on_finished(self, exit_code, exit_status):
        if self.stage == "download":
            if exit_code != 0 and not self.stopping:
                self.log(f"Download failed (exit {exit_code})")

            self.run_next_download()
            return

        if self.stopping:
            self.cleanup_temp()
            self.finish()
            return

        if exit_code != 0:
            self.log(f"Failed: {self.current_source.name} (exit {exit_code})")
            self.cleanup_temp()
            self.stats["failed"] += 1
            self.run_next_convert()
            return

        self.current_temp.rename(self.current_output)
        self.set_progress(100)
        self.log(f"Finished: {self.current_output.name}")
        self.stats["converted"] += 1

        try:
            shutil.move(
                str(self.current_source), str(ARCHIVEV / self.current_source.name)
            )
            self.log(f"Archived: {self.current_source.name}")
        except (OSError, shutil.Error) as e:
            self.log(f"Archive move failed ({e})")

        self.current_source = None
        self.current_temp = None
        self.current_output = None
        self.current_duration = None

        self.run_next_convert()

    def cleanup_temp(self):
        if self.current_temp:
            self.current_temp.unlink(missing_ok=True)
            self.log("Partial file removed.")
            self.current_temp = None

    # --------------------------------------------
    # 종료 / 정리
    # --------------------------------------------

    def stop(self):
        self.stopping = True
        self.status_label.setText(self.tr_("stopped"))
        self.log("")
        self.log("Stop requested.")

        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
        else:
            self.finish()

    def summary_text(self, aborted):
        if aborted:
            return self.tr_(
                "summary_abort",
                converted=self.stats["converted"],
                skipped=self.stats["skipped"],
                failed=self.stats["failed"],
                aborted=aborted,
            )

        return self.tr_(
            "summary",
            converted=self.stats["converted"],
            skipped=self.stats["skipped"],
            failed=self.stats["failed"],
        )

    def notify(self, title, message):
        if self.tray and QSystemTrayIcon.supportsMessages():
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 8000)

    def finish(self):
        self.proc = None
        self.stage = None

        aborted = len(self.convert_queue)
        summary = self.summary_text(aborted)

        self.log("")
        self.log("-" * 50)
        self.log(summary)
        self.log("-" * 50)

        self.convert_queue = []
        self.download_queue = []
        self.total_files = 0
        self.current_index = 0

        self.reset_progress()
        self.status_label.setText(summary)
        self.set_running(False)

        self.notify(
            self.tr_("done_stopped") if self.stopping else self.tr_("done_title"),
            summary,
        )

    def closeEvent(self, event):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                self.tr_("closing"),
                QMessageBox.Yes | QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                event.ignore()
                return

            self.stopping = True
            self.proc.kill()
            self.proc.waitForFinished(3000)
            self.cleanup_temp()

        if self.tray:
            self.tray.hide()

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("konvin")

    window = MainWindow()
    window.show()
    window.check_ffmpeg()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
