#!/usr/bin/env python3

# ============================================
# iPodSync GUI
# Version : v2.0
# Codename: Windowed
# ============================================

import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

VERSION  = "v2.0"
CODENAME = "Windowed"

BASE      = Path.home() / "iPodSync"
TEMPV     = BASE / "tempv"
CHANGEDV  = BASE / "changedv"
ARCHIVEV  = BASE / "archivev"
PLAYLISTV = BASE / "playlistv"

ARCHIVE_FILE = BASE / "download_archive.txt"
CONFIG_FILE  = BASE / "config.json"

for _d in (TEMPV, CHANGEDV, ARCHIVEV, PLAYLISTV):
    _d.mkdir(parents=True, exist_ok=True)

VALID_EXTENSIONS = [".webm", ".mkv", ".mp4", ".avi", ".mov"]

_VENV_YTDLP = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "yt-dlp"
YTDLP = shutil.which("yt-dlp") or (
    str(_VENV_YTDLP) if _VENV_YTDLP.exists() else "yt-dlp"
)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

# iPod Classic 5G: H.264 Baseline Profile Level 3.0, 320x240, 768kbps ceiling
QUALITY_PROFILES = {
    "low": {
        "label":   "Low  (video 384k / audio 96k)",
        "vb":      "384k",
        "maxrate": "512k",
        "bufsize": "1024k",
        "ab":      "96k",
    },
    "medium": {
        "label":   "Medium  (video 700k / audio 128k)",
        "vb":      "700k",
        "maxrate": "768k",
        "bufsize": "1536k",
        "ab":      "128k",
    },
    "high": {
        "label":   "High  (video 768k / audio 160k)",
        "vb":      "768k",
        "maxrate": "768k",
        "bufsize": "1536k",
        "ab":      "160k",
    },
}

DEFAULT_QUALITY = "medium"


def load_quality():
    if not CONFIG_FILE.exists():
        return DEFAULT_QUALITY

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_QUALITY

    quality = data.get("quality", DEFAULT_QUALITY)
    return quality if quality in QUALITY_PROFILES else DEFAULT_QUALITY


def save_quality(quality):
    try:
        CONFIG_FILE.write_text(
            json.dumps({"quality": quality}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def collect_source_files(source_dir):
    files = []

    for file in sorted(source_dir.iterdir()):
        if not file.is_file():
            continue
        if file.name.startswith("."):
            continue
        if file.suffix.lower() not in VALID_EXTENSIONS:
            continue
        files.append(file)

    return files


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


def build_ffmpeg_args(source, dest, quality):
    profile = QUALITY_PROFILES[quality]

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
        "-b:v", profile["vb"],
        "-maxrate", profile["maxrate"],
        "-bufsize", profile["bufsize"],
        "-c:a", "aac",
        "-b:a", profile["ab"],
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        # .part 확장자로는 컨테이너를 추론할 수 없으므로 포맷을 명시
        "-f", "mp4",
        str(dest),
    ]


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"iPodSync {VERSION} ({CODENAME})")
        self.resize(760, 620)

        self.proc = None
        self.stage = None          # "download" | "convert"
        self.stopping = False

        self.download_queue = []
        self.convert_queue = []

        self.current_source = None
        self.current_temp = None
        self.current_output = None

        self.stats = {"converted": 0, "skipped": 0, "failed": 0}

        self._build_ui()

    # --------------------------------------------
    # UI
    # --------------------------------------------

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        # --- 입력 영역 ---
        input_box = QGroupBox("Queue")
        input_layout = QVBoxLayout(input_box)

        mode_row = QHBoxLayout()
        self.radio_video = QRadioButton("Single video")
        self.radio_playlist = QRadioButton("Playlist")
        self.radio_video.setChecked(True)
        mode_row.addWidget(self.radio_video)
        mode_row.addWidget(self.radio_playlist)
        mode_row.addStretch()

        mode_row.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        for key, profile in QUALITY_PROFILES.items():
            self.quality_combo.addItem(profile["label"], key)

        saved = load_quality()
        index = self.quality_combo.findData(saved)
        if index >= 0:
            self.quality_combo.setCurrentIndex(index)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        mode_row.addWidget(self.quality_combo)

        input_layout.addLayout(mode_row)

        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube URL")
        self.url_edit.returnPressed.connect(self.add_url)
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_url)
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self.add_button)
        input_layout.addLayout(url_row)

        self.url_list = QListWidget()
        self.url_list.setMaximumHeight(110)
        input_layout.addWidget(self.url_list)

        list_row = QHBoxLayout()
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.url_list.clear)
        list_row.addWidget(self.remove_button)
        list_row.addWidget(self.clear_button)
        list_row.addStretch()
        input_layout.addLayout(list_row)

        layout.addWidget(input_box)

        # --- 실행 버튼 ---
        action_row = QHBoxLayout()
        self.start_button = QPushButton("Download && Convert")
        self.start_button.clicked.connect(self.start_download)
        self.convert_button = QPushButton("Convert existing files")
        self.convert_button.clicked.connect(self.start_convert_only)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.convert_button)
        action_row.addWidget(self.stop_button)
        layout.addLayout(action_row)

        # --- 로그 ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setFont(QFont("monospace", 9))
        layout.addWidget(self.log_view, stretch=1)

        # --- 상태 표시줄 ---
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(f"Output: {CHANGEDV}"))
        folder_row.addStretch()
        layout.addLayout(folder_row)

        self.setCentralWidget(central)

    def _on_quality_changed(self):
        save_quality(self.quality_combo.currentData())

    # --------------------------------------------
    # 로그 / 상태
    # --------------------------------------------

    def log(self, text):
        self.log_view.appendPlainText(text.rstrip())
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_status(self, text):
        self.status_label.setText(text)

    def set_running(self, running):
        self.start_button.setEnabled(not running)
        self.convert_button.setEnabled(not running)
        self.add_button.setEnabled(not running)
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
        return [
            self.url_list.item(i).text()
            for i in range(self.url_list.count())
        ]

    # --------------------------------------------
    # 실행
    # --------------------------------------------

    def start_download(self):
        urls = self.queued_urls()

        if not urls:
            QMessageBox.information(self, "iPodSync", "URL을 먼저 추가하세요.")
            return

        self.stopping = False
        self.stats = {"converted": 0, "skipped": 0, "failed": 0}
        self.download_queue = list(urls)
        self.convert_queue = []

        self.set_running(True)
        self.log("=" * 50)
        self.log(f"Starting: {len(urls)} URL(s)")
        self.run_next_download()

    def start_convert_only(self):
        files = collect_source_files(TEMPV) + collect_source_files(PLAYLISTV)

        if not files:
            QMessageBox.information(
                self, "iPodSync", "변환할 파일이 없습니다."
            )
            return

        self.stopping = False
        self.stats = {"converted": 0, "skipped": 0, "failed": 0}
        self.download_queue = []
        self.convert_queue = files

        self.set_running(True)
        self.log("=" * 50)
        self.log(f"Converting {len(files)} existing file(s)")
        self.run_next_convert()

    def dest_dir(self):
        return PLAYLISTV if self.radio_playlist.isChecked() else TEMPV

    def run_next_download(self):
        if self.stopping or not self.download_queue:
            self.build_convert_queue()
            return

        url = self.download_queue.pop(0)
        is_playlist = self.radio_playlist.isChecked()

        self.stage = "download"
        self.set_status(f"Downloading: {url}")
        self.log("")
        self.log(f"--- Downloading: {url}")

        self.start_process(YTDLP, build_ytdlp_args(url, self.dest_dir(), is_playlist))

    def build_convert_queue(self):
        if self.stopping:
            self.finish()
            return

        self.convert_queue = collect_source_files(self.dest_dir())

        if not self.convert_queue:
            self.log("")
            self.log("No new files to convert.")
            self.finish()
            return

        self.run_next_convert()

    def run_next_convert(self):
        if self.stopping or not self.convert_queue:
            self.finish()
            return

        source = self.convert_queue.pop(0)
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

        quality = self.quality_combo.currentData()

        self.stage = "convert"
        self.set_status(f"Converting: {source.name}")
        self.log("")
        self.log(f"--- Converting: {source.name}  [{quality}]")

        self.start_process(FFMPEG, build_ffmpeg_args(source, temp_output, quality))

    def start_process(self, program, args):
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_output)
        self.proc.finished.connect(self.on_finished)
        self.proc.errorOccurred.connect(self.on_error)
        self.proc.start(program, args)

    # --------------------------------------------
    # 프로세스 이벤트
    # --------------------------------------------

    def on_output(self):
        if not self.proc:
            return

        data = self.proc.readAllStandardOutput().data()
        text = data.decode("utf-8", errors="replace")

        # ffmpeg 진행률은 \r 로 갱신되므로 줄바꿈으로 바꿔 로그에 남김
        for line in text.replace("\r", "\n").splitlines():
            if line.strip():
                self.log(line)

    def on_error(self, error):
        if error == QProcess.FailedToStart:
            name = "yt-dlp" if self.stage == "download" else "ffmpeg"
            self.log(f"{name} 을(를) 실행할 수 없습니다. 설치 여부를 확인하세요.")
            self.cleanup_temp()
            self.finish()

    def on_finished(self, exit_code, exit_status):
        if self.stage == "download":
            if exit_code != 0 and not self.stopping:
                self.log(f"Download failed (exit {exit_code})")

            self.run_next_download()
            return

        # convert
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
        self.log(f"Finished: {self.current_output.name}")
        self.stats["converted"] += 1

        try:
            shutil.move(str(self.current_source), str(ARCHIVEV / self.current_source.name))
            self.log(f"Archived: {self.current_source.name}")
        except (OSError, shutil.Error) as e:
            self.log(f"Archive move failed ({e})")

        self.current_source = None
        self.current_temp = None
        self.current_output = None

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
        self.set_status("Stopping...")
        self.log("")
        self.log("Stop requested.")

        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
        else:
            self.finish()

    def finish(self):
        self.proc = None
        self.stage = None

        aborted = len(self.convert_queue)

        self.log("")
        self.log("-" * 50)
        self.log(f"Converted : {self.stats['converted']}")
        self.log(f"Skipped   : {self.stats['skipped']}")
        self.log(f"Failed    : {self.stats['failed']}")

        if aborted:
            self.log(f"Aborted   : {aborted}")

        self.log("-" * 50)

        self.convert_queue = []
        self.download_queue = []

        self.set_status("Stopped" if self.stopping else "Ready")
        self.set_running(False)

    def closeEvent(self, event):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            answer = QMessageBox.question(
                self,
                "iPodSync",
                "작업이 진행 중입니다. 종료할까요?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                event.ignore()
                return

            self.stopping = True
            self.proc.kill()
            self.proc.waitForFinished(3000)
            self.cleanup_temp()

        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
