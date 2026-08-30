#!/usr/bin/env python3

# ============================================
# Konvin
# Version : v2.5
# Codename: Namesake
#
# Copyright (c) 2026 장현기 (VertigoJang)
# MIT License — see LICENSE
# https://github.com/VertigoJang/konvin
# ============================================

import json
import re
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
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
VERSION  = "v2.5"
CODENAME = "Namesake"

AUTHOR       = "장현기 (VertigoJang)"
COPYRIGHT    = f"Copyright (c) 2026 {AUTHOR}"
REPO_URL     = "https://github.com/VertigoJang/konvin"
ISSUES_URL   = "https://github.com/VertigoJang/konvin/issues"
DONATE_URL   = "https://buymeacoffee.com/iputaspellonyou"

BASE      = Path.home() / APP_NAME
TEMPV     = BASE / "tempv"
CHANGEDV  = BASE / "changedv"
ARCHIVEV  = BASE / "archivev"
PLAYLISTV = BASE / "playlistv"

ARCHIVE_FILE = BASE / "download_archive.txt"
CONFIG_FILE  = BASE / "config.json"

LEGACY_BASE = Path.home() / "iPodSync"


def migrate_legacy_base():
    """예전 이름(iPodSync) 폴더가 있고 새 폴더가 없으면 그대로 옮긴다."""
    if LEGACY_BASE.exists() and not BASE.exists():
        try:
            LEGACY_BASE.rename(BASE)
        except OSError:
            pass


migrate_legacy_base()

for _d in (TEMPV, CHANGEDV, ARCHIVEV, PLAYLISTV):
    _d.mkdir(parents=True, exist_ok=True)

VALID_EXTENSIONS = [".webm", ".mkv", ".mp4", ".avi", ".mov"]
OUTPUT_EXTENSIONS = [".m4v"]

_VENV_BIN = Path(__file__).resolve().parent.parent / ".venv" / "bin"
_VENV_YTDLP = _VENV_BIN / "yt-dlp"

YTDLP = shutil.which("yt-dlp") or (
    str(_VENV_YTDLP) if _VENV_YTDLP.exists() else "yt-dlp"
)
FFMPEG  = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

# iPod Classic 5G: H.264 Baseline Profile Level 3.0, 320x240, 768kbps ceiling
VIDEO_PROFILES = {
    "low":    {"vb": "384k", "maxrate": "512k", "bufsize": "1024k"},
    "medium": {"vb": "700k", "maxrate": "768k", "bufsize": "1536k"},
    "high":   {"vb": "768k", "maxrate": "768k", "bufsize": "1536k"},
}

AUDIO_PROFILES = {
    "low":    {"ab": "96k"},
    "medium": {"ab": "128k"},
    "high":   {"ab": "160k"},
}

DEFAULT_VIDEO = "medium"
DEFAULT_AUDIO = "medium"
DEFAULT_LANGUAGE = "ko"

COLLAPSED_HEIGHT = 360
EXPANDED_HEIGHT  = 680

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

        "video_low":      "낮음 (384k)",
        "video_medium":   "보통 (700k)",
        "video_high":     "높음 (768k)",
        "audio_low":      "낮음 (96k)",
        "audio_medium":   "보통 (128k)",
        "audio_high":     "높음 (160k)",

        "language":       "언어:",
        "settings_title": "설정",
        "tab_general":    "일반",
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

        "folder_tempv":     "tempv — 단일 영상 원본",
        "folder_playlistv": "playlistv — 재생목록 원본",
        "folder_changedv":  "changedv — 변환 완료 영상",
        "folder_archivev":  "archivev — 변환 후 보관된 원본",

        "path_tempv":     "단일 영상으로 받은 원본이 임시로 저장됩니다.",
        "path_playlistv": "재생목록으로 받은 원본이 임시로 저장됩니다.",
        "path_changedv":  "변환이 끝난 영상이 저장됩니다. 아이팟에 넣을 파일입니다.",
        "path_archivev":  "변환이 끝난 뒤 원본이 이곳으로 옮겨집니다.",
        "path_archive_file": "이미 받은 영상의 목록입니다. 같은 영상을 두 번 받지 않게 합니다.",
        "path_config":    "언어와 화질 설정이 저장됩니다.",

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
    },
    "en": {
        "language_name":  "English",
        "queue":          "Queue",
        "single_video":   "Single video",
        "playlist":       "Playlist",
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

        "video_low":      "Low (384k)",
        "video_medium":   "Medium (700k)",
        "video_high":     "High (768k)",
        "audio_low":      "Low (96k)",
        "audio_medium":   "Medium (128k)",
        "audio_high":     "High (160k)",

        "language":       "Language:",
        "settings_title": "Settings",
        "tab_general":    "General",
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

        "folder_tempv":     "tempv — single video originals",
        "folder_playlistv": "playlistv — playlist originals",
        "folder_changedv":  "changedv — converted videos",
        "folder_archivev":  "archivev — originals kept after conversion",

        "path_tempv":     "Originals downloaded as single videos are stored here.",
        "path_playlistv": "Originals downloaded from playlists are stored here.",
        "path_changedv":  "Converted videos land here. These are the files for your iPod.",
        "path_archivev":  "Originals move here once conversion succeeds.",
        "path_archive_file": "A list of videos already downloaded, so the same one isn't fetched twice.",
        "path_config":    "Your language and quality settings are stored here.",

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
    },
}


HELP_SECTIONS = {
    "ko": [
        ("단일 영상 / 재생목록",
         "받으려는 주소의 종류를 고릅니다. 재생목록을 고르면 주소에 묶인 영상을 "
         "전부 받고, 파일 이름 앞에 001, 002 같은 순번이 붙습니다. 단일 영상을 "
         "고르면 주소에 재생목록이 섞여 있어도 영상 하나만 받습니다."),

        ("영상 / 소리",
         "화면과 소리의 품질을 따로 고릅니다. 클릭휠 아이팟이 재생할 수 있는 범위 "
         "안에서 각각 세 단계가 있고, 원하는 대로 조합할 수 있습니다. 음악 위주의 "
         "영상이라면 영상을 낮게, 소리를 높게 두는 식입니다. 어느 쪽을 골라도 화면 "
         "크기는 320×240으로 같으며, 여기서 고른 값은 이번에 처리할 파일 전체에 "
         "적용됩니다."),

        ("설정",
         "언어를 바꾸고, 쌓인 파일을 정리하고, 폴더 위치와 프로그램 정보를 확인할 "
         "수 있습니다. 바꾼 설정은 바로 적용되고 다음에 프로그램을 켤 때도 "
         "유지됩니다."),

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

        ("설정 › 정리",
         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "
         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 원본을 "
         "지워도 이미 변환된 영상은 남고, 반대로 변환된 영상을 지우면 원본이 "
         "남아 있는 한 다시 변환할 수 있습니다. 삭제는 되돌릴 수 없습니다."),

        ("설정 › 정보",
         "만든 사람, 라이선스, 소스 코드 주소를 볼 수 있습니다. 버그 신고 링크와 "
         "후원 링크도 여기에 있습니다."),
    ],
    "en": [
        ("Single video / Playlist",
         "Choose what kind of link you're adding. Playlist downloads every video "
         "in the link and prefixes filenames with 001, 002 and so on. Single video "
         "grabs just the one video, even if the link also points at a playlist."),

        ("Video / Audio",
         "Picture and sound quality are chosen separately. Each has three steps, "
         "all within what a click-wheel iPod can play, and you can mix them "
         "freely — low video with high audio suits a music video, for instance. "
         "The picture size is 320x240 either way, and your choice applies to every "
         "file in the current run."),

        ("Settings",
         "Change the language, clear out accumulated files, and see where things "
         "are stored along with program information. Changes take effect "
         "immediately and are remembered next time."),

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

        ("Settings › Cleanup",
         "Deletes video files that have piled up. Pick a folder to see its contents "
         "and total size, then remove individual files or empty it entirely. "
         "Deleting originals leaves your converted videos untouched, and deleting "
         "converted videos still lets you reconvert as long as the originals "
         "remain. Deletion cannot be undone."),

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
        "video_quality": DEFAULT_VIDEO,
        "audio_quality": DEFAULT_AUDIO,
        "language": DEFAULT_LANGUAGE,
    }

    if not CONFIG_FILE.exists():
        return config

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return config

    if data.get("video_quality") in VIDEO_PROFILES:
        config["video_quality"] = data["video_quality"]
    elif data.get("quality") in VIDEO_PROFILES:
        config["video_quality"] = data["quality"]

    if data.get("audio_quality") in AUDIO_PROFILES:
        config["audio_quality"] = data["audio_quality"]
    elif data.get("quality") in AUDIO_PROFILES:
        config["audio_quality"] = data["quality"]

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
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


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


def build_ytdlp_args(url, dest_dir, is_playlist):
    if is_playlist:
        template = str(dest_dir / "%(playlist_index|000)03d - %(title)s [%(id)s].%(ext)s")
    else:
        template = str(dest_dir / "%(title)s [%(id)s].%(ext)s")

    args = [
        "-f", "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "-o", template,
        "--no-overwrites",
        "--trim-filenames", "200",
        "--download-archive", str(ARCHIVE_FILE),
        "--newline",
    ]

    if is_playlist:
        args += ["--yes-playlist", "--ignore-errors"]
    else:
        args += ["--no-playlist"]

    args.append(url)
    return args


def build_ffmpeg_args(source, dest, video_quality, audio_quality):
    video = VIDEO_PROFILES[video_quality]
    audio = AUDIO_PROFILES[audio_quality]

    return [
        "-y",
        "-i", str(source),
        "-vf",
        "scale=320:240:force_original_aspect_ratio=decrease,"
        "pad=320:240:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", video["vb"],
        "-maxrate", video["maxrate"],
        "-bufsize", video["bufsize"],
        "-c:a", "aac",
        "-b:a", audio["ab"],
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        # .part 확장자로는 컨테이너를 추론할 수 없으므로 포맷을 명시
        "-f", "mp4",
        str(dest),
    ]


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

        self.reload()

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
# 설정 창
# ============================================

class SettingsDialog(QDialog):

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = dict(config)

        texts = TEXTS[self.config["language"]]
        self.setWindowTitle(texts["settings_title"])
        self.resize(580, 500)

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
        general_layout.addStretch()
        tabs.addTab(general, texts["tab_general"])

        # --- 정리 ---
        tabs.addTab(CleanupTab(self, texts), texts["tab_cleanup"])

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

    def result_config(self):
        return {"language": self.language_combo.currentData()}


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
        for key in VIDEO_PROFILES:
            self.video_combo.addItem("", key)
        self.video_combo.currentIndexChanged.connect(self._on_quality_changed)
        mode_row.addWidget(self.video_combo)

        self.audio_label = QLabel()
        mode_row.addWidget(self.audio_label)

        self.audio_combo = QComboBox()
        for key in AUDIO_PROFILES:
            self.audio_combo.addItem("", key)
        self.audio_combo.currentIndexChanged.connect(self._on_quality_changed)
        mode_row.addWidget(self.audio_combo)

        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_settings)
        mode_row.addWidget(self.settings_button)

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

        self.folder_button = QPushButton()
        self.folder_button.clicked.connect(lambda: open_folder(CHANGEDV))
        bottom_row.addWidget(self.folder_button)

        layout.addLayout(bottom_row)

        self.setCentralWidget(central)
        self.resize(880, COLLAPSED_HEIGHT)

    def _build_tray(self):
        self.tray = None

        icon_path = Path(__file__).resolve().parent.parent / "assets" / "konvin.png"

        if icon_path.exists():
            from PySide6.QtGui import QIcon
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
    # 언어 적용
    # --------------------------------------------

    def tr_(self, key, **kwargs):
        text = TEXTS[self.config["language"]].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def retranslate(self):
        self.setWindowTitle(f"{APP_NAME} {VERSION} ({CODENAME})")

        self.queue_box.setTitle(self.tr_("queue"))
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
        self.folder_button.setText(self.tr_("open_folder"))
        self.output_label.setText(self.tr_("output_path", path=CHANGEDV))

        self.log_button.setText(
            self.tr_("hide_log") if self.log_view.isVisible() else self.tr_("show_log")
        )

        self._retranslate_combo(self.video_combo, "video", self.config["video_quality"])
        self._retranslate_combo(self.audio_combo, "audio", self.config["audio_quality"])

        if not self.proc:
            self.status_label.setText(self.tr_("ready"))

    def _retranslate_combo(self, combo, prefix, current):
        combo.blockSignals(True)

        for i in range(combo.count()):
            key = combo.itemData(i)
            combo.setItemText(i, self.tr_(f"{prefix}_{key}"))

        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)

        combo.blockSignals(False)

    def open_settings(self):
        dialog = SettingsDialog(self, self.config)

        if dialog.exec() != QDialog.Accepted:
            return

        self.config.update(dialog.result_config())
        save_config(self.config)
        self.retranslate()

    def open_help(self):
        HelpDialog(self, self.config["language"]).exec()

    def _on_quality_changed(self):
        self.config["video_quality"] = self.video_combo.currentData()
        self.config["audio_quality"] = self.audio_combo.currentData()
        save_config(self.config)

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

    def start_download(self):
        urls = self.queued_urls()

        if not urls:
            QMessageBox.information(self, APP_NAME, self.tr_("no_url"))
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
            build_ytdlp_args(url, self.dest_dir(), self.radio_playlist.isChecked()),
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

        video_quality = self.video_combo.currentData()
        audio_quality = self.audio_combo.currentData()

        self.stage = "convert"
        self.status_label.setText(f"{self.tr_('converting')}: {source.name}")
        self.set_counter(self.current_index, self.total_files)
        self.set_progress(0)
        self.set_eta(None)
        self.log("")
        self.log(
            f"--- Converting: {source.name}  "
            f"[video {video_quality} / audio {audio_quality}]"
        )

        self.start_process(
            FFMPEG,
            build_ffmpeg_args(source, temp_output, video_quality, audio_quality),
        )

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
