#!/usr/bin/env python3
"""
Konvin v3.0 — 정리 기능을 독립 창으로 빼고 다운로드 기록 초기화를 넣는다.

리포 루트에서 실행:
    python packaging/patch_cleanup.py
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
    'VERSION  = "v2.9"',
    'VERSION  = "v3.0"',
    "버전 v3.0",
)

replace_once(
    'CODENAME = "Packaged"',
    'CODENAME = "Tidy"',
    "코드네임",
)

# --- 2. 문자열 추가 (한국어) ---
replace_once(
    '''        "cleanup_nothing_selected": "삭제할 파일을 선택하세요.",''',
    '''        "cleanup_nothing_selected": "삭제할 파일을 선택하세요.",
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
            "다운로드 기록 {count}개를 지웁니다.\\n"
            "이후 같은 영상을 다시 받을 수 있게 됩니다. 계속할까요?",
        "record_done":     "기록을 초기화했습니다.",''',
    "한국어 문자열",
)

# --- 3. 문자열 추가 (영어) ---
replace_once(
    '''        "cleanup_nothing_selected": "Select the files you want to delete.",''',
    '''        "cleanup_nothing_selected": "Select the files you want to delete.",
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
            "Clear {count} download record(s).\\n"
            "You'll be able to download those videos again. Continue?",
        "record_done":     "History cleared.",''',
    "영어 문자열",
)

# --- 4. 정리 탭에 기록 초기화 영역 추가 ---
replace_once(
    '''        button_row = QHBoxLayout()
        self.delete_selected_button = QPushButton(texts["cleanup_delete_selected"])
        self.delete_selected_button.clicked.connect(self.delete_selected)
        self.delete_all_button = QPushButton(texts["cleanup_delete_all"])
        self.delete_all_button.clicked.connect(self.delete_all)
        button_row.addWidget(self.delete_selected_button)
        button_row.addWidget(self.delete_all_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.reload()''',
    '''        button_row = QHBoxLayout()
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
        self.reload_record()''',
    "기록 초기화 영역",
)

# --- 5. 기록 관련 메서드 추가 ---
replace_once(
    '''    def delete_all(self):
        paths = self.all_paths()

        if not paths:
            return

        folder, _ = self.current_folder()''',
    '''    def record_entries(self):
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

        folder, _ = self.current_folder()''',
    "기록 메서드",
)

# --- 6. 정리 창 클래스 추가 ---
replace_once(
    '''# ============================================
# 설정 창
# ============================================

class SettingsDialog(QDialog):''',
    '''# ============================================
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

class SettingsDialog(QDialog):''',
    "정리 창 클래스",
)

# --- 7. 설정 창에서 정리 탭 제거 ---
replace_once(
    '''        # --- 정리 ---
        tabs.addTab(CleanupTab(self, texts), texts["tab_cleanup"])

''',
    "",
    "설정 정리 탭 제거",
)

# --- 8. 메인 창 아래줄에 정리 버튼 추가 ---
replace_once(
    '''        self.output_label = QLabel()
        bottom_row.addWidget(self.output_label, stretch=1)

        self.folder_button = QPushButton()
        self.folder_button.clicked.connect(lambda: open_folder(CHANGEDV))
        bottom_row.addWidget(self.folder_button)''',
    '''        self.output_label = QLabel()
        bottom_row.addWidget(self.output_label, stretch=1)

        self.cleanup_button = QPushButton()
        self.cleanup_button.clicked.connect(self.open_cleanup)
        bottom_row.addWidget(self.cleanup_button)

        self.folder_button = QPushButton()
        self.folder_button.clicked.connect(lambda: open_folder(CHANGEDV))
        bottom_row.addWidget(self.folder_button)''',
    "정리 버튼",
)

# --- 9. 버튼 라벨 번역 ---
replace_once(
    '''        self.folder_button.setText(self.tr_("open_folder"))''',
    '''        self.cleanup_button.setText(self.tr_("cleanup_button"))
        self.folder_button.setText(self.tr_("open_folder"))''',
    "버튼 라벨",
)

# --- 10. 정리 창 여는 메서드 ---
replace_once(
    '''    def open_help(self):
        HelpDialog(self, self.config["language"]).exec()''',
    '''    def open_help(self):
        HelpDialog(self, self.config["language"]).exec()

    def open_cleanup(self):
        CleanupDialog(self, TEXTS[self.config["language"]]).exec()''',
    "정리 창 열기",
)

# --- 11. 작업 중에는 정리 버튼 비활성화 ---
replace_once(
    '''        self.settings_button.setEnabled(not running)
        self.device_combo.setEnabled(not running)''',
    '''        self.settings_button.setEnabled(not running)
        self.cleanup_button.setEnabled(not running)
        self.device_combo.setEnabled(not running)''',
    "실행 중 비활성화",
)

# --- 12. 도움말 갱신 (한국어) ---
replace_once(
    '''        ("설정 › 정리",
         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "
         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 원본을 "
         "지워도 이미 변환된 영상은 남고, 반대로 변환된 영상을 지우면 원본이 "
         "남아 있는 한 다시 변환할 수 있습니다. 삭제는 되돌릴 수 없습니다."),''',
    '''        ("파일 정리",
         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "
         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 삭제는 "
         "되돌릴 수 없습니다.\\n\\n"
         "아래쪽의 다운로드 기록은 이미 받은 영상의 목록입니다. 폴더에서 파일을 "
         "지워도 이 기록은 남아 있어서, 같은 영상을 다시 받으려 하면 건너뜁니다. "
         "다시 받고 싶다면 기록을 초기화하세요."),''',
    "도움말 (한국어)",
)

# --- 13. 도움말 갱신 (영어) ---
replace_once(
    '''        ("Settings › Cleanup",
         "Deletes video files that have piled up. Pick a folder to see its contents "
         "and total size, then remove individual files or empty it entirely. "
         "Deleting originals leaves your converted videos untouched, and deleting "
         "converted videos still lets you reconvert as long as the originals "
         "remain. Deletion cannot be undone."),''',
    '''        ("Clean up",
         "Deletes video files that have piled up. Pick a folder to see its contents "
         "and total size, then remove individual files or empty it entirely. "
         "Deletion cannot be undone.\\n\\n"
         "The download history below lists videos you've already fetched. Deleting "
         "the files doesn't clear it, so the same video will be skipped next time. "
         "Reset the history if you want to download it again."),''',
    "도움말 (영어)",
)

path.write_text(text, encoding="utf-8")
print("완료")
