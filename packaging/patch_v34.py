#!/usr/bin/env python3
"""
Konvin v3.0 → v3.4 통합 패치

한 번에 네 가지를 넣는다.

  v3.1  파일 이름 정규화 — 아이팟이 표시하지 못하는 글자를 일반 문자로
  v3.2  다시 변환 — 보관된 원본을 골라 다시 만들기, 이름 충돌 처리
  v3.3  다운로드 전 확인 — 이미 받은 영상이면 물어보기, 기록 버튼 제거
  v3.4  새 버전 확인 — 시작할 때 릴리스 조회, 알림 창

리포 루트에서 실행:
    python packaging/patch_v34.py
"""

from pathlib import Path

path = Path("scripts/konvin.py")
text = path.read_text(encoding="utf-8")


def sub(old, new, label):
    global text

    count = text.count(old)

    if count != 1:
        raise SystemExit(f"[중단] {label}: {count} 곳에서 발견 (1 이어야 함)")

    text = text.replace(old, new)
    print(f"  {label}")


print("패치 중...")


# ============================================
# 공통 — 버전과 임포트
# ============================================

sub('VERSION  = "v3.0"', 'VERSION  = "v3.4"', "버전 v3.4")
sub('CODENAME = "Tidy"', 'CODENAME = "Uptodate"', "코드네임")

sub(
    "import urllib.request\nimport zipfile",
    "import unicodedata\nimport urllib.request\nimport zipfile",
    "unicodedata 임포트",
)

sub(
    "    QApplication,\n    QComboBox,",
    "    QApplication,\n    QCheckBox,\n    QComboBox,",
    "QCheckBox 임포트",
)

sub(
    'DONATE_URL = "https://buymeacoffee.com/iputaspellonyou"',
    'DONATE_URL = "https://buymeacoffee.com/iputaspellonyou"\n'
    'RELEASES_URL = "https://github.com/VertigoJang/konvin/releases/latest"\n'
    'RELEASE_API  = "https://api.github.com/repos/VertigoJang/konvin/releases/latest"',
    "릴리스 주소",
)


# ============================================
# 설정 값
# ============================================

sub(
    'ASPECT_MODES = ("letterbox", "preserve")',
    'ASPECT_MODES = ("letterbox", "preserve")\nFILENAME_MODES = ("safe", "raw")',
    "파일 이름 모드",
)

sub(
    'DEFAULT_LANGUAGE = "ko"',
    'DEFAULT_FILENAME = "safe"\n'
    "DEFAULT_CHECK_UPDATES = True\n"
    'DEFAULT_LANGUAGE = "ko"',
    "기본값",
)

sub(
    '        "aspect": DEFAULT_ASPECT,\n        "language": DEFAULT_LANGUAGE,',
    '        "aspect": DEFAULT_ASPECT,\n'
    '        "filename": DEFAULT_FILENAME,\n'
    '        "check_updates": DEFAULT_CHECK_UPDATES,\n'
    '        "skip_version": "",\n'
    '        "language": DEFAULT_LANGUAGE,',
    "설정 기본값",
)

sub(
    '    if data.get("aspect") in ASPECT_MODES:\n'
    '        config["aspect"] = data["aspect"]',
    '    if data.get("aspect") in ASPECT_MODES:\n'
    '        config["aspect"] = data["aspect"]\n'
    "\n"
    '    if data.get("filename") in FILENAME_MODES:\n'
    '        config["filename"] = data["filename"]\n'
    "\n"
    '    if isinstance(data.get("check_updates"), bool):\n'
    '        config["check_updates"] = data["check_updates"]\n'
    "\n"
    '    if isinstance(data.get("skip_version"), str):\n'
    '        config["skip_version"] = data["skip_version"]',
    "설정 읽기",
)


# ============================================
# 문자열
# ============================================

sub(
    '        "record_title":    "다운로드 기록",',
    '        "reconvert":      "다시 변환",\n'
    '        "reconvert_title": "다시 변환",\n'
    '        "reconvert_hint":\n'
    '            "변환을 마친 뒤 보관해 둔 원본입니다. 다른 기기나 다른 화질로 "\n'
    '            "다시 만들고 싶을 때 고르세요. 지금 설정된 기기와 화질이 그대로 "\n'
    '            "적용됩니다.",\n'
    '        "reconvert_empty": "보관된 원본이 없습니다.",\n'
    '        "reconvert_select_all": "전체 선택",\n'
    '        "reconvert_select_none": "선택 해제",\n'
    '        "reconvert_start": "선택한 파일 변환",\n'
    '        "reconvert_selected": "{count}개 선택됨",\n'
    '        "reconvert_nothing": "변환할 파일을 선택하세요.",\n'
    "\n"
    '        "conflict_title":  "같은 이름의 파일이 있습니다",\n'
    '        "conflict_body":\n'
    '            "{name}\\n\\n이미 변환된 파일이 있습니다. 어떻게 할까요?",\n'
    '        "conflict_overwrite": "덮어쓰기",\n'
    '        "conflict_rename":    "다른 이름으로 저장",\n'
    '        "conflict_skip":      "건너뛰기",\n'
    '        "conflict_apply_all": "남은 파일에도 같은 선택 적용",\n'
    "\n"
    '        "checking":        "이미 받은 영상인지 확인하는 중...",\n'
    '        "dl_conflict_title": "이미 받은 영상입니다",\n'
    '        "dl_conflict_one":\n'
    '            "{url}\\n\\n이 영상은 전에 받은 적이 있습니다. 어떻게 할까요?",\n'
    '        "dl_conflict_many":\n'
    '            "{url}\\n\\n이 재생목록에서 {count}개는 전에 받은 적이 있습니다. "\n'
    '            "어떻게 할까요?",\n'
    '        "dl_redownload":   "다시 받기",\n'
    '        "dl_skip":         "건너뛰기",\n'
    "\n"
    '        "filename":       "파일 이름:",\n'
    '        "filename_safe":  "아이팟이 읽을 수 있게 정리 (권장)",\n'
    '        "filename_raw":   "원래 제목 그대로",\n'
    '        "filename_hint":\n'
    '            "유튜브 제목에는 분위기를 내려고 특수한 글씨체나 이모지를 쓰는 "\n'
    '            "경우가 많습니다. 아이팟 클래식에는 그 글자가 없어 목록에서 "\n'
    '            "빈칸으로 보입니다. 정리를 켜면 일반 문자로 바꾸고 이모지는 "\n'
    '            "지웁니다.",\n'
    "\n"
    '        "update_check":    "새 버전 확인",\n'
    '        "update_auto":     "시작할 때 새 버전이 있는지 확인",\n'
    '        "update_title":    "새 버전이 나왔습니다",\n'
    '        "update_body":     "지금 쓰는 버전은 {current} 이고, {latest} 이 나왔습니다.",\n'
    '        "update_open":     "릴리스 페이지 열기",\n'
    '        "update_later":    "나중에",\n'
    '        "update_skip":     "이 버전은 다시 알리지 않기",\n'
    '        "update_none":     "최신 버전을 쓰고 있습니다.",\n'
    '        "update_failed":   "확인하지 못했습니다: {error}",\n'
    '        "update_checking": "확인하는 중...",\n'
    "\n"
    '        "record_title":    "다운로드 기록",',
    "문자열 (한국어)",
)

sub(
    '        "record_title":    "Download history",',
    '        "reconvert":      "Convert again",\n'
    '        "reconvert_title": "Convert again",\n'
    '        "reconvert_hint":\n'
    '            "Originals kept after conversion. Pick the ones you want to remake "\n'
    '            "for a different device or quality — the settings currently "\n'
    '            "selected will be used.",\n'
    '        "reconvert_empty": "No originals kept yet.",\n'
    '        "reconvert_select_all": "Select all",\n'
    '        "reconvert_select_none": "Clear selection",\n'
    '        "reconvert_start": "Convert selected",\n'
    '        "reconvert_selected": "{count} selected",\n'
    '        "reconvert_nothing": "Select the files you want to convert.",\n'
    "\n"
    '        "conflict_title":  "A file with that name exists",\n'
    '        "conflict_body":\n'
    '            "{name}\\n\\nThis has already been converted. What would you like "\n'
    '            "to do?",\n'
    '        "conflict_overwrite": "Overwrite",\n'
    '        "conflict_rename":    "Save under a new name",\n'
    '        "conflict_skip":      "Skip",\n'
    '        "conflict_apply_all": "Do the same for the remaining files",\n'
    "\n"
    '        "checking":        "Checking what\'s already been downloaded...",\n'
    '        "dl_conflict_title": "Already downloaded",\n'
    '        "dl_conflict_one":\n'
    '            "{url}\\n\\nYou\'ve downloaded this before. What would you like "\n'
    '            "to do?",\n'
    '        "dl_conflict_many":\n'
    '            "{url}\\n\\n{count} video(s) in this playlist have been downloaded "\n'
    '            "before. What would you like to do?",\n'
    '        "dl_redownload":   "Download again",\n'
    '        "dl_skip":         "Skip",\n'
    "\n"
    '        "filename":       "Filenames:",\n'
    '        "filename_safe":  "Clean up for the iPod (recommended)",\n'
    '        "filename_raw":   "Keep the original title",\n'
    '        "filename_hint":\n'
    '            "YouTube titles often use styled letters or emoji for effect. The "\n'
    '            "iPod classic has no glyphs for those, so they show up as blanks "\n'
    '            "in the list. Cleaning up converts them to plain characters and "\n'
    '            "drops emoji.",\n'
    "\n"
    '        "update_check":    "Check for updates",\n'
    '        "update_auto":     "Check for a new version on startup",\n'
    '        "update_title":    "A new version is available",\n'
    '        "update_body":     "You have {current}; {latest} is out.",\n'
    '        "update_open":     "Open the release page",\n'
    '        "update_later":    "Later",\n'
    '        "update_skip":     "Don\'t tell me about this version again",\n'
    '        "update_none":     "You\'re on the latest version.",\n'
    '        "update_failed":   "Couldn\'t check: {error}",\n'
    '        "update_checking": "Checking...",\n'
    "\n"
    '        "record_title":    "Download history",',
    "문자열 (영어)",
)


# ============================================
# v3.1 — 파일 이름 정규화
# ============================================

sub(
    "def format_size(num_bytes):",
    "# 아이팟 폰트에 없는 기호를 비슷한 아스키로 바꾼다. NFKD 로도 분해되지\n"
    "# 않는 것들이다.\n"
    "SYMBOL_MAP = {\n"
    '    "\\u29f8": "/", "\\u29f9": "\\\\", "\\uff0f": "/", "\\uff3c": "\\\\",\n'
    '    "\\uff5c": "|", "\\u2215": "/", "\\u2044": "/",\n'
    "    \"\\u201c\": '\\\"', \"\\u201d\": '\\\"', \"\\u201e\": '\\\"', \"\\u201f\": '\\\"',\n"
    '    "\\u2018": "\'", "\\u2019": "\'", "\\u201a": "\'", "\\u201b": "\'",\n'
    '    "\\u2013": "-", "\\u2014": "-", "\\u2015": "-", "\\u2010": "-",\n'
    '    "\\u2026": "...", "\\u2022": "-", "\\u00b7": "-", "\\u2027": "-",\n'
    "    \"\\u00ab\": '\\\"', \"\\u00bb\": '\\\"', \"\\u2039\": \"'\", \"\\u203a\": \"'\",\n"
    '    "\\u2605": "*", "\\u2606": "*", "\\u266a": "", "\\u266b": "",\n'
    '    "\\u2192": "->", "\\u2190": "<-", "\\u2194": "<->",\n'
    '    "\\u00d7": "x", "\\u00f7": "/", "\\u00b1": "+/-",\n'
    '    "\\u00a9": "(c)", "\\u00ae": "(R)", "\\u2122": "(TM)",\n'
    '    "\\u200b": "", "\\u200c": "", "\\u200d": "", "\\ufeff": "",\n'
    '    "\\u00a0": " ",\n'
    "}\n"
    "\n"
    "\n"
    "def ipod_safe_text(value):\n"
    '    """아이팟 클래식이 표시할 수 있는 문자만 남긴다.\n'
    "\n"
    "    유튜브 제목에 흔한 수학 볼드·이탤릭이나 전각 문자는 일반 알파벳과 다른\n"
    "    코드포인트라 기기 폰트에 없다. NFKD 로 기본 형태로 되돌린 뒤, 한글이\n"
    "    자모로 쪼개진 것은 NFC 로 다시 합친다. 이모지처럼 대응되는 문자가 없는\n"
    "    것은 지운다.\n"
    '    """\n'
    "    if not value:\n"
    "        return value\n"
    "\n"
    "    for source, target in SYMBOL_MAP.items():\n"
    "        value = value.replace(source, target)\n"
    "\n"
    '    value = unicodedata.normalize("NFKD", value)\n'
    "\n"
    "    kept = []\n"
    "\n"
    "    for char in value:\n"
    "        category = unicodedata.category(char)\n"
    "\n"
    "        # 결합 문자는 남겨 두어야 NFC 로 한글이 다시 합쳐진다\n"
    '        if category.startswith("M"):\n'
    "            kept.append(char)\n"
    "            continue\n"
    "\n"
    "        # 기호·그림 영역(이모지 등)은 버린다\n"
    '        if category in ("So", "Sk", "Cf", "Co", "Cn"):\n'
    "            continue\n"
    "\n"
    "        if ord(char) > 0xFFFF:\n"
    "            continue\n"
    "\n"
    "        kept.append(char)\n"
    "\n"
    '    value = unicodedata.normalize("NFC", "".join(kept))\n'
    '    value = re.sub(r"\\s+", " ", value).strip()\n'
    "    value = re.sub(r'[<>:\"/\\\\\\\\|?*]', \"_\", value)\n"
    "\n"
    '    return value or "untitled"\n'
    "\n"
    "\n"
    "def format_size(num_bytes):",
    "정규화 함수",
)


# ============================================
# v3.3 — 기록 파일 다루기와 조회 스레드
# ============================================

sub(
    "def build_ytdlp_args(",
    "# 유튜브 주소에서 영상 아이디를 뽑는다\n"
    "YOUTUBE_ID_RE = re.compile(\n"
    '    r"(?:youtu\\.be/|youtube\\.com/(?:watch\\?(?:.*&)?v=|shorts/|embed/|live/|v/))"\n'
    '    r"([A-Za-z0-9_-]{11})"\n'
    ")\n"
    "\n"
    "\n"
    "def read_archive_ids():\n"
    '    """이미 받은 영상 아이디 모음. 기록 파일은 \'youtube ID\' 형식이다."""\n'
    "    if not ARCHIVE_FILE.exists():\n"
    "        return set()\n"
    "\n"
    "    ids = set()\n"
    "\n"
    "    try:\n"
    '        for line in ARCHIVE_FILE.read_text(encoding="utf-8").splitlines():\n'
    "            parts = line.split()\n"
    "\n"
    "            if len(parts) >= 2:\n"
    "                ids.add(parts[1])\n"
    "    except OSError:\n"
    "        pass\n"
    "\n"
    "    return ids\n"
    "\n"
    "\n"
    "def remove_archive_ids(ids):\n"
    '    """다시 받기로 정한 영상을 기록에서 뺀다."""\n'
    "    if not ids or not ARCHIVE_FILE.exists():\n"
    "        return\n"
    "\n"
    "    try:\n"
    '        lines = ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()\n'
    "    except OSError:\n"
    "        return\n"
    "\n"
    "    kept = []\n"
    "\n"
    "    for line in lines:\n"
    "        parts = line.split()\n"
    "\n"
    "        if len(parts) >= 2 and parts[1] in ids:\n"
    "            continue\n"
    "\n"
    "        if line.strip():\n"
    "            kept.append(line)\n"
    "\n"
    "    try:\n"
    "        ARCHIVE_FILE.write_text(\n"
    '            "\\n".join(kept) + ("\\n" if kept else ""), encoding="utf-8"\n'
    "        )\n"
    "    except OSError:\n"
    "        pass\n"
    "\n"
    "\n"
    "def extract_video_id(url):\n"
    '    """단일 영상 주소에서 아이디를 뽑는다. 못 뽑으면 None."""\n'
    "    match = YOUTUBE_ID_RE.search(url)\n"
    "    return match.group(1) if match else None\n"
    "\n"
    "\n"
    "def version_tuple(value):\n"
    '    """\'v3.4\' 나 \'3.4.1\' 을 비교할 수 있는 숫자 묶음으로."""\n'
    '    numbers = re.findall(r"\\d+", value or "")\n'
    "    return tuple(int(n) for n in numbers) if numbers else (0,)\n"
    "\n"
    "\n"
    "def ssl_context():\n"
    '    """macOS 의 파이썬은 시스템 인증서를 쓰지 않아 검증이 실패한다."""\n'
    "    try:\n"
    "        import certifi\n"
    "        import ssl\n"
    "\n"
    "        return ssl.create_default_context(cafile=certifi.where())\n"
    "    except ImportError:\n"
    "        return None\n"
    "\n"
    "\n"
    "class IdResolver(QObject):\n"
    '    """주소마다 어떤 영상이 들어 있는지 미리 알아본다.\n'
    "\n"
    "    단일 영상은 주소만 보면 되지만, 재생목록은 안에 무엇이 있는지 조회해야\n"
    "    하므로 네트워크를 쓴다. 그래서 별도 스레드에서 돈다.\n"
    '    """\n'
    "\n"
    "    finished = Signal(list)\n"
    "\n"
    "    def __init__(self, urls, is_playlist):\n"
    "        super().__init__()\n"
    "        self.urls = list(urls)\n"
    "        self.is_playlist = is_playlist\n"
    "\n"
    "    def run(self):\n"
    "        results = []\n"
    "\n"
    "        for url in self.urls:\n"
    "            if self.is_playlist:\n"
    "                results.append((url, self._playlist_ids(url)))\n"
    "                continue\n"
    "\n"
    "            found = extract_video_id(url)\n"
    "            results.append((url, [found] if found else []))\n"
    "\n"
    "        self.finished.emit(results)\n"
    "\n"
    "    def _playlist_ids(self, url):\n"
    "        try:\n"
    "            result = subprocess.run(\n"
    "                [\n"
    "                    YTDLP,\n"
    '                    "--flat-playlist",\n'
    '                    "--no-warnings",\n'
    '                    "--print", "%(id)s",\n'
    "                    url,\n"
    "                ],\n"
    "                capture_output=True,\n"
    "                text=True,\n"
    "                timeout=120,\n"
    "                **hidden_process_kwargs(),\n"
    "            )\n"
    "        except (OSError, subprocess.SubprocessError):\n"
    "            return []\n"
    "\n"
    "        return [\n"
    "            line.strip() for line in result.stdout.splitlines() if line.strip()\n"
    "        ]\n"
    "\n"
    "\n"
    "class UpdateChecker(QObject):\n"
    '    """GitHub 릴리스를 조회해 새 버전이 있는지 본다."""\n'
    "\n"
    "    finished = Signal(str, str)\n"
    "\n"
    "    def run(self):\n"
    "        request = urllib.request.Request(\n"
    "            RELEASE_API,\n"
    "            headers={\n"
    '                "User-Agent": f"{APP_NAME}/{VERSION}",\n'
    '                "Accept": "application/vnd.github+json",\n'
    "            },\n"
    "        )\n"
    "\n"
    "        try:\n"
    "            with urllib.request.urlopen(\n"
    "                request, timeout=10, context=ssl_context()\n"
    "            ) as response:\n"
    '                data = json.loads(response.read().decode("utf-8"))\n'
    "        except Exception as e:\n"
    '            self.finished.emit("", str(e))\n'
    "            return\n"
    "\n"
    '        self.finished.emit(data.get("tag_name", ""), "")\n'
    "\n"
    "\n"
    "def build_ytdlp_args(",
    "기록 함수와 스레드",
)


# ============================================
# 새 창들
# ============================================

sub(
    "# ============================================\n# 정리 창\n# ============================================",
    "# ============================================\n"
    "# 새 버전 알림 창\n"
    "# ============================================\n"
    "\n"
    "class UpdateDialog(QDialog):\n"
    "\n"
    "    def __init__(self, parent, texts, latest):\n"
    "        super().__init__(parent)\n"
    "\n"
    "        self.texts = texts\n"
    "        self.latest = latest\n"
    "\n"
    '        self.setWindowTitle(texts["update_title"])\n'
    "        self.setMinimumWidth(440)\n"
    "\n"
    "        layout = QVBoxLayout(self)\n"
    "        layout.setSpacing(12)\n"
    "\n"
    "        body = QLabel(\n"
    '            texts["update_body"].format(current=VERSION, latest=latest)\n'
    "        )\n"
    "        body.setWordWrap(True)\n"
    "        layout.addWidget(body)\n"
    "\n"
    '        self.skip_box = QCheckBox(texts["update_skip"])\n'
    "        layout.addWidget(self.skip_box)\n"
    "\n"
    "        button_row = QHBoxLayout()\n"
    "\n"
    '        open_button = QPushButton(texts["update_open"])\n'
    "        open_button.clicked.connect(self._open)\n"
    "        open_button.setDefault(True)\n"
    "\n"
    '        later = QPushButton(texts["update_later"])\n'
    "        later.clicked.connect(self.accept)\n"
    "\n"
    "        button_row.addWidget(open_button)\n"
    "        button_row.addWidget(later)\n"
    "        layout.addLayout(button_row)\n"
    "\n"
    "    def _open(self):\n"
    "        open_url(RELEASES_URL)\n"
    "        self.accept()\n"
    "\n"
    "    def should_skip(self):\n"
    "        return self.skip_box.isChecked()\n"
    "\n"
    "\n"
    "# ============================================\n"
    "# 다운로드 충돌 창\n"
    "# ============================================\n"
    "\n"
    "class DownloadConflictDialog(QDialog):\n"
    '    """이미 받은 영상일 때 어떻게 할지 묻는다."""\n'
    "\n"
    '    REDOWNLOAD = "redownload"\n'
    '    SKIP = "skip"\n'
    "\n"
    "    def __init__(self, parent, texts, url, count, remaining):\n"
    "        super().__init__(parent)\n"
    "\n"
    "        self.texts = texts\n"
    "        self.choice = self.SKIP\n"
    "\n"
    '        self.setWindowTitle(texts["dl_conflict_title"])\n'
    "        self.setMinimumWidth(480)\n"
    "\n"
    "        layout = QVBoxLayout(self)\n"
    "        layout.setSpacing(12)\n"
    "\n"
    "        if count > 1:\n"
    '            message = texts["dl_conflict_many"].format(url=url, count=count)\n'
    "        else:\n"
    '            message = texts["dl_conflict_one"].format(url=url)\n'
    "\n"
    "        body = QLabel(message)\n"
    "        body.setWordWrap(True)\n"
    "        body.setTextInteractionFlags(Qt.TextSelectableByMouse)\n"
    "        layout.addWidget(body)\n"
    "\n"
    '        self.apply_all = QCheckBox(texts["conflict_apply_all"])\n'
    "        self.apply_all.setEnabled(remaining > 0)\n"
    "        layout.addWidget(self.apply_all)\n"
    "\n"
    "        button_row = QHBoxLayout()\n"
    "\n"
    '        again = QPushButton(texts["dl_redownload"])\n'
    "        again.clicked.connect(lambda: self._choose(self.REDOWNLOAD))\n"
    "\n"
    '        skip = QPushButton(texts["dl_skip"])\n'
    "        skip.clicked.connect(lambda: self._choose(self.SKIP))\n"
    "        skip.setDefault(True)\n"
    "\n"
    "        button_row.addWidget(again)\n"
    "        button_row.addWidget(skip)\n"
    "        layout.addLayout(button_row)\n"
    "\n"
    "    def _choose(self, choice):\n"
    "        self.choice = choice\n"
    "        self.accept()\n"
    "\n"
    "    def result_choice(self):\n"
    "        return self.choice, self.apply_all.isChecked()\n"
    "\n"
    "\n"
    "# ============================================\n"
    "# 파일 충돌 창\n"
    "# ============================================\n"
    "\n"
    "class ConflictDialog(QDialog):\n"
    '    """이미 변환된 결과물이 있을 때 어떻게 할지 묻는다."""\n'
    "\n"
    '    OVERWRITE = "overwrite"\n'
    '    RENAME = "rename"\n'
    '    SKIP = "skip"\n'
    "\n"
    "    def __init__(self, parent, texts, name, remaining):\n"
    "        super().__init__(parent)\n"
    "\n"
    "        self.texts = texts\n"
    "        self.choice = self.SKIP\n"
    "\n"
    '        self.setWindowTitle(texts["conflict_title"])\n'
    "        self.setMinimumWidth(460)\n"
    "\n"
    "        layout = QVBoxLayout(self)\n"
    "        layout.setSpacing(12)\n"
    "\n"
    '        body = QLabel(texts["conflict_body"].format(name=name))\n'
    "        body.setWordWrap(True)\n"
    "        body.setTextInteractionFlags(Qt.TextSelectableByMouse)\n"
    "        layout.addWidget(body)\n"
    "\n"
    '        self.apply_all = QCheckBox(texts["conflict_apply_all"])\n'
    "        self.apply_all.setEnabled(remaining > 0)\n"
    "        layout.addWidget(self.apply_all)\n"
    "\n"
    "        button_row = QHBoxLayout()\n"
    "\n"
    '        overwrite = QPushButton(texts["conflict_overwrite"])\n'
    "        overwrite.clicked.connect(lambda: self._choose(self.OVERWRITE))\n"
    "\n"
    '        rename = QPushButton(texts["conflict_rename"])\n'
    "        rename.clicked.connect(lambda: self._choose(self.RENAME))\n"
    "        rename.setDefault(True)\n"
    "\n"
    '        skip = QPushButton(texts["conflict_skip"])\n'
    "        skip.clicked.connect(lambda: self._choose(self.SKIP))\n"
    "\n"
    "        button_row.addWidget(overwrite)\n"
    "        button_row.addWidget(rename)\n"
    "        button_row.addWidget(skip)\n"
    "        layout.addLayout(button_row)\n"
    "\n"
    "    def _choose(self, choice):\n"
    "        self.choice = choice\n"
    "        self.accept()\n"
    "\n"
    "    def result_choice(self):\n"
    "        return self.choice, self.apply_all.isChecked()\n"
    "\n"
    "\n"
    "# ============================================\n"
    "# 다시 변환 창\n"
    "# ============================================\n"
    "\n"
    "class ReconvertDialog(QDialog):\n"
    '    """보관된 원본 중에서 다시 변환할 것을 고른다."""\n'
    "\n"
    "    def __init__(self, parent, texts):\n"
    "        super().__init__(parent)\n"
    "\n"
    "        self.texts = texts\n"
    "        self.selected = []\n"
    "\n"
    '        self.setWindowTitle(texts["reconvert_title"])\n'
    "        self.resize(560, 520)\n"
    "\n"
    "        layout = QVBoxLayout(self)\n"
    "\n"
    '        hint = QLabel(texts["reconvert_hint"])\n'
    "        hint.setWordWrap(True)\n"
    '        hint.setStyleSheet("color: gray;")\n'
    "        layout.addWidget(hint)\n"
    "\n"
    "        self.file_list = QListWidget()\n"
    "        layout.addWidget(self.file_list, stretch=1)\n"
    "\n"
    '        self.count_label = QLabel("")\n'
    "        layout.addWidget(self.count_label)\n"
    "\n"
    "        select_row = QHBoxLayout()\n"
    "\n"
    '        all_button = QPushButton(texts["reconvert_select_all"])\n'
    "        all_button.clicked.connect(lambda: self._set_all(Qt.Checked))\n"
    "\n"
    '        none_button = QPushButton(texts["reconvert_select_none"])\n'
    "        none_button.clicked.connect(lambda: self._set_all(Qt.Unchecked))\n"
    "\n"
    "        select_row.addWidget(all_button)\n"
    "        select_row.addWidget(none_button)\n"
    "        select_row.addStretch()\n"
    "        layout.addLayout(select_row)\n"
    "\n"
    "        buttons = QDialogButtonBox()\n"
    "        self.start_button = buttons.addButton(\n"
    '            texts["reconvert_start"], QDialogButtonBox.AcceptRole\n'
    "        )\n"
    "        buttons.addButton(QDialogButtonBox.Cancel)\n"
    "        buttons.accepted.connect(self._accept)\n"
    "        buttons.rejected.connect(self.reject)\n"
    "        layout.addWidget(buttons)\n"
    "\n"
    "        self._load()\n"
    "\n"
    "    def _load(self):\n"
    "        files = collect_source_files(ARCHIVEV)\n"
    "\n"
    "        for file in files:\n"
    "            try:\n"
    "                size = file.stat().st_size\n"
    "            except OSError:\n"
    "                size = 0\n"
    "\n"
    '            item = QListWidgetItem(f"{file.name}   ({format_size(size)})")\n'
    "            item.setData(Qt.UserRole, str(file))\n"
    "            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)\n"
    "            item.setCheckState(Qt.Unchecked)\n"
    "            self.file_list.addItem(item)\n"
    "\n"
    "        if not files:\n"
    '            self.count_label.setText(self.texts["reconvert_empty"])\n'
    "            self.start_button.setEnabled(False)\n"
    "        else:\n"
    "            self.file_list.itemChanged.connect(self._update_count)\n"
    "            self._update_count()\n"
    "\n"
    "    def _set_all(self, state):\n"
    "        for i in range(self.file_list.count()):\n"
    "            self.file_list.item(i).setCheckState(state)\n"
    "\n"
    "    def _checked_paths(self):\n"
    "        paths = []\n"
    "\n"
    "        for i in range(self.file_list.count()):\n"
    "            item = self.file_list.item(i)\n"
    "\n"
    "            if item.checkState() == Qt.Checked:\n"
    "                paths.append(Path(item.data(Qt.UserRole)))\n"
    "\n"
    "        return paths\n"
    "\n"
    "    def _update_count(self):\n"
    "        count = len(self._checked_paths())\n"
    "        self.count_label.setText(\n"
    '            self.texts["reconvert_selected"].format(count=count)\n'
    "        )\n"
    "\n"
    "    def _accept(self):\n"
    "        paths = self._checked_paths()\n"
    "\n"
    "        if not paths:\n"
    "            QMessageBox.information(\n"
    '                self, APP_NAME, self.texts["reconvert_nothing"]\n'
    "            )\n"
    "            return\n"
    "\n"
    "        self.selected = paths\n"
    "        self.accept()\n"
    "\n"
    "\n"
    "# ============================================\n"
    "# 정리 창\n"
    "# ============================================",
    "새 창 세 개",
)


# ============================================
# v3.3 — 정리 탭에서 기록 영역 제거
# ============================================

sub(
    "        # --- 다운로드 기록 ---\n"
    '        record_box = QGroupBox(texts["record_title"])\n'
    "        record_layout = QVBoxLayout(record_box)\n"
    "\n"
    '        record_hint = QLabel(texts["record_hint"])\n'
    "        record_hint.setWordWrap(True)\n"
    '        record_hint.setStyleSheet("color: gray;")\n'
    "        record_layout.addWidget(record_hint)\n"
    "\n"
    "        record_row = QHBoxLayout()\n"
    '        self.record_label = QLabel("")\n'
    "        record_row.addWidget(self.record_label, stretch=1)\n"
    "\n"
    '        self.record_button = QPushButton(texts["record_reset"])\n'
    "        self.record_button.clicked.connect(self.reset_record)\n"
    "        record_row.addWidget(self.record_button)\n"
    "\n"
    "        record_layout.addLayout(record_row)\n"
    "        layout.addWidget(record_box)\n"
    "\n"
    "        self.reload()\n"
    "        self.reload_record()",
    "        self.reload()",
    "기록 영역 제거",
)

sub(
    "    def record_entries(self):\n"
    "        if not ARCHIVE_FILE.exists():\n"
    "            return 0\n"
    "\n"
    "        try:\n"
    '            lines = ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()\n'
    "        except OSError:\n"
    "            return 0\n"
    "\n"
    "        return len([line for line in lines if line.strip()])\n"
    "\n"
    "    def reload_record(self):\n"
    "        count = self.record_entries()\n"
    "\n"
    "        if count:\n"
    "            self.record_label.setText(\n"
    '                self.texts["record_count"].format(count=count)\n'
    "            )\n"
    "        else:\n"
    '            self.record_label.setText(self.texts["record_empty"])\n'
    "\n"
    "        self.record_button.setEnabled(bool(count))\n"
    "\n"
    "    def reset_record(self):\n"
    "        count = self.record_entries()\n"
    "\n"
    "        if not count:\n"
    "            return\n"
    "\n"
    "        answer = QMessageBox.question(\n"
    "            self,\n"
    "            APP_NAME,\n"
    '            self.texts["record_confirm"].format(count=count),\n'
    "            QMessageBox.Yes | QMessageBox.No,\n"
    "            QMessageBox.No,\n"
    "        )\n"
    "\n"
    "        if answer != QMessageBox.Yes:\n"
    "            return\n"
    "\n"
    "        try:\n"
    "            ARCHIVE_FILE.unlink(missing_ok=True)\n"
    "        except OSError as e:\n"
    "            QMessageBox.warning(self, APP_NAME, str(e))\n"
    "            return\n"
    "\n"
    "        self.reload_record()\n"
    '        QMessageBox.information(self, APP_NAME, self.texts["record_done"])\n'
    "\n"
    "    def delete_all(self):",
    "    def delete_all(self):",
    "기록 메서드 제거",
)


# ============================================
# 설정 창 — 파일 이름, 업데이트
# ============================================

sub(
    "        encoding_layout.addWidget(codec_box)\n        encoding_layout.addStretch()",
    "        encoding_layout.addWidget(codec_box)\n"
    "\n"
    '        filename_box = QGroupBox(texts["filename"])\n'
    "        filename_layout = QVBoxLayout(filename_box)\n"
    "\n"
    "        self.filename_combo = QComboBox()\n"
    "        for mode in FILENAME_MODES:\n"
    '            self.filename_combo.addItem(texts[f"filename_{mode}"], mode)\n'
    "\n"
    '        index = self.filename_combo.findData(self.config["filename"])\n'
    "        if index >= 0:\n"
    "            self.filename_combo.setCurrentIndex(index)\n"
    "\n"
    "        filename_layout.addWidget(self.filename_combo)\n"
    "\n"
    '        filename_hint = QLabel(texts["filename_hint"])\n'
    "        filename_hint.setWordWrap(True)\n"
    '        filename_hint.setStyleSheet("color: gray;")\n'
    "        filename_layout.addWidget(filename_hint)\n"
    "\n"
    "        encoding_layout.addWidget(filename_box)\n"
    "        encoding_layout.addStretch()",
    "인코딩 탭 항목",
)

sub(
    "        general_layout.addWidget(ffmpeg_box)\n        general_layout.addStretch()",
    "        general_layout.addWidget(ffmpeg_box)\n"
    "\n"
    '        update_box = QGroupBox(texts["update_check"])\n'
    "        update_layout = QVBoxLayout(update_box)\n"
    "\n"
    '        self.update_auto_box = QCheckBox(texts["update_auto"])\n'
    '        self.update_auto_box.setChecked(self.config["check_updates"])\n'
    "        update_layout.addWidget(self.update_auto_box)\n"
    "\n"
    "        update_row = QHBoxLayout()\n"
    '        self.update_button = QPushButton(texts["update_check"])\n'
    "        self.update_button.clicked.connect(self.check_updates_now)\n"
    "        update_row.addWidget(self.update_button)\n"
    "\n"
    '        self.update_status = QLabel("")\n'
    "        self.update_status.setWordWrap(True)\n"
    '        self.update_status.setStyleSheet("color: gray;")\n'
    "        update_row.addWidget(self.update_status, stretch=1)\n"
    "\n"
    "        update_layout.addLayout(update_row)\n"
    "        general_layout.addWidget(update_box)\n"
    "\n"
    "        general_layout.addStretch()",
    "일반 탭 항목",
)

sub(
    "    def result_config(self):\n"
    "        return {\n"
    '            "language": self.language_combo.currentData(),\n'
    '            "aspect": self.aspect_combo.currentData(),\n'
    '            "codec": self.codec_combo.currentData(),\n'
    "        }",
    "    def check_updates_now(self):\n"
    "        self.update_button.setEnabled(False)\n"
    '        self.update_status.setText(self.texts["update_checking"])\n'
    "\n"
    "        self.update_thread = QThread(self)\n"
    "        self.update_worker = UpdateChecker()\n"
    "        self.update_worker.moveToThread(self.update_thread)\n"
    "\n"
    "        self.update_thread.started.connect(self.update_worker.run)\n"
    "        self.update_worker.finished.connect(self._on_update_checked)\n"
    "\n"
    "        self.update_thread.start()\n"
    "\n"
    "    def _on_update_checked(self, latest, error):\n"
    "        self.update_thread.quit()\n"
    "        self.update_thread.wait()\n"
    "        self.update_thread = None\n"
    "        self.update_worker = None\n"
    "\n"
    "        self.update_button.setEnabled(True)\n"
    "\n"
    "        if error:\n"
    "            self.update_status.setText(\n"
    '                self.texts["update_failed"].format(error=error)\n'
    "            )\n"
    "            return\n"
    "\n"
    "        if latest and version_tuple(latest) > version_tuple(VERSION):\n"
    '            self.update_status.setText("")\n'
    "            UpdateDialog(self, self.texts, latest).exec()\n"
    "            return\n"
    "\n"
    '        self.update_status.setText(self.texts["update_none"])\n'
    "\n"
    "    def result_config(self):\n"
    "        return {\n"
    '            "language": self.language_combo.currentData(),\n'
    '            "aspect": self.aspect_combo.currentData(),\n'
    '            "codec": self.codec_combo.currentData(),\n'
    '            "filename": self.filename_combo.currentData(),\n'
    '            "check_updates": self.update_auto_box.isChecked(),\n'
    "        }",
    "설정 확인 동작",
)


# ============================================
# 메인 창 — 버튼과 상태
# ============================================

sub(
    "        self.convert_button = QPushButton()\n"
    "        self.convert_button.clicked.connect(self.start_convert_only)\n"
    "        self.stop_button = QPushButton()",
    "        self.convert_button = QPushButton()\n"
    "        self.convert_button.clicked.connect(self.start_convert_only)\n"
    "        self.reconvert_button = QPushButton()\n"
    "        self.reconvert_button.clicked.connect(self.start_reconvert)\n"
    "        self.stop_button = QPushButton()",
    "다시 변환 버튼",
)

sub(
    "        action_row.addWidget(self.convert_button)\n"
    "        action_row.addWidget(self.stop_button)",
    "        action_row.addWidget(self.convert_button)\n"
    "        action_row.addWidget(self.reconvert_button)\n"
    "        action_row.addWidget(self.stop_button)",
    "버튼 배치",
)

sub(
    '        self.convert_button.setText(self.tr_("convert_only"))',
    '        self.convert_button.setText(self.tr_("convert_only"))\n'
    '        self.reconvert_button.setText(self.tr_("reconvert"))',
    "버튼 라벨",
)

sub(
    "        self.convert_button.setEnabled(not running)\n"
    "        self.add_button.setEnabled(not running)",
    "        self.convert_button.setEnabled(not running)\n"
    "        self.reconvert_button.setEnabled(not running)\n"
    "        self.add_button.setEnabled(not running)",
    "실행 중 비활성화",
)

sub(
    "        self.collapsed_height = COLLAPSED_HEIGHT",
    "        self.collapsed_height = COLLAPSED_HEIGHT\n"
    "\n"
    "        # 다시 변환 중에는 원본을 옮기지 않는다\n"
    "        self.reconverting = False\n"
    "        self.conflict_choice = None\n"
    "\n"
    "        self.resolve_thread = None\n"
    "        self.resolver = None\n"
    "        self.update_thread = None\n"
    "        self.update_worker = None",
    "상태 변수",
)


# ============================================
# 메인 창 — 동작
# ============================================

sub(
    "    def check_ffmpeg(self):",
    "    def check_updates(self):\n"
    '        """시작할 때 조용히 확인한다. 실패해도 아무 말 하지 않는다."""\n'
    '        if not self.config.get("check_updates", True):\n'
    "            return\n"
    "\n"
    "        self.update_thread = QThread(self)\n"
    "        self.update_worker = UpdateChecker()\n"
    "        self.update_worker.moveToThread(self.update_thread)\n"
    "\n"
    "        self.update_thread.started.connect(self.update_worker.run)\n"
    "        self.update_worker.finished.connect(self.on_update_checked)\n"
    "\n"
    "        self.update_thread.start()\n"
    "\n"
    "    def on_update_checked(self, latest, error):\n"
    "        self.update_thread.quit()\n"
    "        self.update_thread.wait()\n"
    "        self.update_thread = None\n"
    "        self.update_worker = None\n"
    "\n"
    "        if error or not latest:\n"
    "            return\n"
    "\n"
    "        if version_tuple(latest) <= version_tuple(VERSION):\n"
    "            return\n"
    "\n"
    '        if latest == self.config.get("skip_version"):\n'
    "            return\n"
    "\n"
    '        dialog = UpdateDialog(self, TEXTS[self.config["language"]], latest)\n'
    "        dialog.exec()\n"
    "\n"
    "        if dialog.should_skip():\n"
    '            self.config["skip_version"] = latest\n'
    "            save_config(self.config)\n"
    "\n"
    "    def check_ffmpeg(self):",
    "자동 업데이트 확인",
)

sub(
    "    def start_download(self):\n"
    "        urls = self.queued_urls()\n"
    "\n"
    "        if not urls:\n"
    '            QMessageBox.information(self, APP_NAME, self.tr_("no_url"))\n'
    "            return\n"
    "\n"
    "        if not self.require_ffmpeg():\n"
    "            return\n"
    "\n"
    "        self.stopping = False\n"
    '        self.stats = {"converted": 0, "skipped": 0, "failed": 0}\n'
    "        self.download_queue = list(urls)\n"
    "        self.convert_queue = []\n"
    "        self.total_files = len(urls)\n"
    "        self.current_index = 0\n"
    "\n"
    "        self.set_running(True)\n"
    "        self.reset_progress()\n"
    '        self.log("=" * 50)\n'
    "        self.run_next_download()",
    "    def start_download(self):\n"
    "        urls = self.queued_urls()\n"
    "\n"
    "        if not urls:\n"
    '            QMessageBox.information(self, APP_NAME, self.tr_("no_url"))\n'
    "            return\n"
    "\n"
    "        if not self.require_ffmpeg():\n"
    "            return\n"
    "\n"
    "        self.stopping = False\n"
    "        self.reconverting = False\n"
    '        self.stats = {"converted": 0, "skipped": 0, "failed": 0}\n'
    "        self.convert_queue = []\n"
    "        self.current_index = 0\n"
    "\n"
    "        self.set_running(True)\n"
    "        self.reset_progress()\n"
    '        self.log("=" * 50)\n'
    "\n"
    "        # 무엇을 이미 받았는지 먼저 알아본다\n"
    '        self.status_label.setText(self.tr_("checking"))\n'
    "\n"
    "        self.resolve_thread = QThread(self)\n"
    "        self.resolver = IdResolver(urls, self.radio_playlist.isChecked())\n"
    "        self.resolver.moveToThread(self.resolve_thread)\n"
    "\n"
    "        self.resolve_thread.started.connect(self.resolver.run)\n"
    "        self.resolver.finished.connect(self.on_ids_resolved)\n"
    "\n"
    "        self.resolve_thread.start()\n"
    "\n"
    "    def on_ids_resolved(self, results):\n"
    "        self.resolve_thread.quit()\n"
    "        self.resolve_thread.wait()\n"
    "        self.resolve_thread = None\n"
    "        self.resolver = None\n"
    "\n"
    "        if self.stopping:\n"
    "            self.finish()\n"
    "            return\n"
    "\n"
    "        known = read_archive_ids()\n"
    "        queue = []\n"
    "        to_forget = set()\n"
    "        choice = None\n"
    "\n"
    "        for index, (url, ids) in enumerate(results):\n"
    "            seen = [video_id for video_id in ids if video_id in known]\n"
    "\n"
    "            if not seen:\n"
    "                queue.append(url)\n"
    "                continue\n"
    "\n"
    "            if choice is None:\n"
    "                dialog = DownloadConflictDialog(\n"
    "                    self,\n"
    '                    TEXTS[self.config["language"]],\n'
    "                    url,\n"
    "                    len(seen),\n"
    "                    len(results) - index - 1,\n"
    "                )\n"
    "                dialog.exec()\n"
    "                picked, apply_all = dialog.result_choice()\n"
    "\n"
    "                if apply_all:\n"
    "                    choice = picked\n"
    "            else:\n"
    "                picked = choice\n"
    "\n"
    "            if picked == DownloadConflictDialog.REDOWNLOAD:\n"
    "                to_forget.update(seen)\n"
    "                queue.append(url)\n"
    "            else:\n"
    '                self.log(f"Skipped (already downloaded): {url}")\n'
    "\n"
    "        remove_archive_ids(to_forget)\n"
    "\n"
    "        if not queue:\n"
    '            self.log("")\n'
    '            self.log(self.tr_("no_new_files"))\n'
    "            self.finish()\n"
    "            return\n"
    "\n"
    "        self.download_queue = queue\n"
    "        self.total_files = len(queue)\n"
    "        self.current_index = 0\n"
    "        self.run_next_download()\n"
    "\n"
    "    def start_reconvert(self):\n"
    "        if not collect_source_files(ARCHIVEV):\n"
    "            QMessageBox.information(\n"
    '                self, APP_NAME, self.tr_("reconvert_empty")\n'
    "            )\n"
    "            return\n"
    "\n"
    '        dialog = ReconvertDialog(self, TEXTS[self.config["language"]])\n'
    "\n"
    "        if dialog.exec() != QDialog.Accepted:\n"
    "            return\n"
    "\n"
    "        if not self.require_ffmpeg():\n"
    "            return\n"
    "\n"
    "        self.stopping = False\n"
    "        self.reconverting = True\n"
    "        self.conflict_choice = None\n"
    '        self.stats = {"converted": 0, "skipped": 0, "failed": 0}\n'
    "        self.download_queue = []\n"
    "        self.convert_queue = list(dialog.selected)\n"
    "        self.total_files = len(self.convert_queue)\n"
    "        self.current_index = 0\n"
    "\n"
    "        self.set_running(True)\n"
    "        self.reset_progress()\n"
    '        self.log("=" * 50)\n'
    "        self.run_next_convert()\n"
    "\n"
    "    def resolve_conflict(self, output):\n"
    '        """이미 결과물이 있을 때 어떻게 할지 정한다.\n'
    "\n"
    "        돌아오는 값은 실제로 쓸 경로이며, 건너뛰기를 고르면 None 이다.\n"
    '        """\n'
    "        if not output.exists():\n"
    "            return output\n"
    "\n"
    "        choice = self.conflict_choice\n"
    "\n"
    "        if choice is None:\n"
    "            dialog = ConflictDialog(\n"
    "                self,\n"
    '                TEXTS[self.config["language"]],\n'
    "                output.name,\n"
    "                len(self.convert_queue),\n"
    "            )\n"
    "            dialog.exec()\n"
    "            choice, apply_all = dialog.result_choice()\n"
    "\n"
    "            if apply_all:\n"
    "                self.conflict_choice = choice\n"
    "\n"
    "        if choice == ConflictDialog.SKIP:\n"
    "            return None\n"
    "\n"
    "        if choice == ConflictDialog.OVERWRITE:\n"
    "            return output\n"
    "\n"
    "        stem = output.stem\n"
    "        index = 2\n"
    "\n"
    "        while True:\n"
    '            candidate = output.with_name(f"{stem} ({index}){output.suffix}")\n'
    "\n"
    "            if not candidate.exists():\n"
    "                return candidate\n"
    "\n"
    "            index += 1",
    "다운로드 사전 확인과 다시 변환",
)

sub(
    "        self.stopping = False\n"
    '        self.stats = {"converted": 0, "skipped": 0, "failed": 0}\n'
    "        self.download_queue = []\n"
    "        self.convert_queue = files",
    "        self.stopping = False\n"
    "        self.reconverting = False\n"
    '        self.stats = {"converted": 0, "skipped": 0, "failed": 0}\n'
    "        self.download_queue = []\n"
    "        self.convert_queue = files",
    "받아둔 파일 변환 플래그",
)

sub(
    '        output = CHANGEDV / f"{source.stem}_iPod.m4v"\n'
    "\n"
    "        if output.exists():\n"
    '            self.log(f"Skipped (already exists): {output.name}")\n'
    '            self.stats["skipped"] += 1\n'
    "            self.run_next_convert()\n"
    "            return\n"
    "\n"
    '        temp_output = CHANGEDV / f".{source.stem}_iPod.m4v.part"',
    '        if self.config["filename"] == "safe":\n'
    "            safe_stem = ipod_safe_text(source.stem)\n"
    "        else:\n"
    "            safe_stem = source.stem\n"
    "\n"
    '        output = CHANGEDV / f"{safe_stem}_iPod.m4v"\n'
    "\n"
    "        if self.reconverting:\n"
    "            resolved = self.resolve_conflict(output)\n"
    "\n"
    "            if resolved is None:\n"
    '                self.log(f"Skipped: {output.name}")\n'
    '                self.stats["skipped"] += 1\n'
    "                self.run_next_convert()\n"
    "                return\n"
    "\n"
    "            output = resolved\n"
    "        elif output.exists():\n"
    '            self.log(f"Skipped (already exists): {output.name}")\n'
    '            self.stats["skipped"] += 1\n'
    "            self.run_next_convert()\n"
    "            return\n"
    "\n"
    '        temp_output = CHANGEDV / f".{output.stem}.m4v.part"',
    "변환 이름과 충돌 처리",
)

sub(
    "        try:\n"
    "            shutil.move(\n"
    "                str(self.current_source), str(ARCHIVEV / self.current_source.name)\n"
    "            )\n"
    '            self.log(f"Archived: {self.current_source.name}")\n'
    "        except (OSError, shutil.Error) as e:\n"
    '            self.log(f"Archive move failed ({e})")',
    "        # 다시 변환일 때는 원본이 이미 보관 폴더에 있다\n"
    "        if not self.reconverting:\n"
    "            try:\n"
    "                shutil.move(\n"
    "                    str(self.current_source),\n"
    "                    str(ARCHIVEV / self.current_source.name),\n"
    "                )\n"
    '                self.log(f"Archived: {self.current_source.name}")\n'
    "            except (OSError, shutil.Error) as e:\n"
    '                self.log(f"Archive move failed ({e})")',
    "원본 보존",
)

sub(
    "        self.reset_progress()\n"
    "        self.status_label.setText(summary)\n"
    "        self.set_running(False)",
    "        self.reconverting = False\n"
    "        self.conflict_choice = None\n"
    "\n"
    "        self.reset_progress()\n"
    "        self.status_label.setText(summary)\n"
    "        self.set_running(False)",
    "상태 초기화",
)

sub(
    "    window.show()\n    window.check_ffmpeg()",
    "    window.show()\n    window.check_ffmpeg()\n    window.check_updates()",
    "시작 시 호출",
)


# ============================================
# 도움말
# ============================================

sub(
    '        ("파일 정리",\n'
    '         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "\n'
    '         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 삭제는 "\n'
    '         "되돌릴 수 없습니다.\\n\\n"\n'
    '         "아래쪽의 다운로드 기록은 이미 받은 영상의 목록입니다. 폴더에서 파일을 "\n'
    '         "지워도 이 기록은 남아 있어서, 같은 영상을 다시 받으려 하면 건너뜁니다. "\n'
    '         "다시 받고 싶다면 기록을 초기화하세요."),',
    '        ("다시 변환",\n'
    '         "변환을 마친 뒤 보관해 둔 원본을 다시 변환합니다. 다른 기기용으로 "\n'
    '         "만들거나 화질을 바꾸고 싶을 때 쓰면 됩니다. 버튼을 누르면 보관된 "\n'
    '         "원본 목록이 뜨고, 필요한 것만 골라 변환할 수 있습니다.\\n\\n"\n'
    '         "이미 같은 이름의 결과물이 있으면 덮어쓸지, 다른 이름으로 둘지, "\n'
    '         "건너뛸지 물어봅니다."),\n'
    "\n"
    '        ("이미 받은 영상",\n'
    '         "한 번 받은 영상은 기록에 남습니다. 같은 주소를 다시 넣으면 프로그램이 "\n'
    '         "알아채고 다시 받을지 건너뛸지 물어봅니다. 재생목록은 안에 든 영상까지 "\n'
    '         "미리 확인하므로, 목록의 일부만 새로 추가된 경우에도 필요한 것만 "\n'
    '         "받습니다."),\n'
    "\n"
    '        ("파일 이름 정리",\n'
    '         "유튜브 제목에는 분위기를 내려고 특수한 글씨체를 쓰는 경우가 많습니다. "\n'
    '         "겉보기에는 기울임체나 굵은 글씨 같지만 실제로는 전혀 다른 문자이며, "\n'
    '         "아이팟 클래식의 폰트에는 그 글자가 없어 목록에서 아무것도 보이지 "\n'
    '         "않습니다. 이모지도 마찬가지입니다.\\n\\n"\n'
    '         "기본값으로 이런 문자를 일반 알파벳과 숫자로 바꾸고 이모지는 지웁니다. "\n'
    '         "한글과 일반 문자는 그대로 남습니다. 설정 › 인코딩에서 끌 수 있습니다."),\n'
    "\n"
    '        ("새 버전 확인",\n'
    '         "프로그램을 켤 때 새 버전이 나왔는지 조용히 확인합니다. 있으면 알림 "\n'
    '         "창이 뜨고, 릴리스 페이지를 열어 내려받을 수 있습니다. 특정 버전을 "\n'
    '         "다시 알리지 않게 하거나, 설정 › 일반에서 확인 자체를 끌 수 있습니다."),\n'
    "\n"
    '        ("파일 정리",\n'
    '         "폴더에 쌓인 영상 파일을 지웁니다. 폴더를 고르면 파일 목록과 전체 용량이 "\n'
    '         "보이고, 필요한 것만 골라 지우거나 한 번에 비울 수 있습니다. 삭제는 "\n'
    '         "되돌릴 수 없습니다."),',
    "도움말 (한국어)",
)

sub(
    '        ("Clean up",\n'
    '         "Deletes video files that have piled up. Pick a folder to see its contents "\n'
    '         "and total size, then remove individual files or empty it entirely. "\n'
    '         "Deletion cannot be undone.\\n\\n"\n'
    '         "The download history below lists videos you\'ve already fetched. Deleting "\n'
    '         "the files doesn\'t clear it, so the same video will be skipped next time. "\n'
    '         "Reset the history if you want to download it again."),',
    '        ("Convert again",\n'
    '         "Reconverts originals kept after a previous run — useful for making a "\n'
    '         "version for a different iPod or at a different quality. The button "\n'
    '         "opens a list of kept originals so you can pick just the ones you "\n'
    '         "want.\\n\\n"\n'
    '         "If a converted file with the same name already exists, you\'ll be "\n'
    '         "asked whether to overwrite it, save under a new name, or skip it."),\n'
    "\n"
    '        ("Already downloaded",\n'
    '         "Videos you\'ve fetched are remembered. Add the same link again and "\n'
    '         "Konvin notices, asking whether to download it again or skip it. "\n'
    '         "Playlists are checked item by item, so if only part of a list is new, "\n'
    '         "only that part is fetched."),\n'
    "\n"
    '        ("Filename cleanup",\n'
    '         "YouTube titles often use styled letters for effect. They look like "\n'
    '         "italics or bold, but they are entirely different characters, and the "\n'
    '         "iPod classic has no glyphs for them — the entry shows up blank in the "\n'
    '         "list. The same goes for emoji.\\n\\n"\n'
    '         "By default these are converted to plain letters and digits, and emoji "\n'
    '         "are dropped. Korean and ordinary characters are left alone. You can "\n'
    '         "turn this off in Settings > Encoding."),\n'
    "\n"
    '        ("Checking for updates",\n'
    '         "On startup Konvin quietly checks whether a newer version is out. If "\n'
    '         "there is one, a dialog offers to open the release page. You can "\n'
    '         "dismiss a particular version for good, or turn the check off entirely "\n'
    '         "in Settings > General."),\n'
    "\n"
    '        ("Clean up",\n'
    '         "Deletes video files that have piled up. Pick a folder to see its contents "\n'
    '         "and total size, then remove individual files or empty it entirely. "\n'
    '         "Deletion cannot be undone."),',
    "도움말 (영어)",
)


path.write_text(text, encoding="utf-8")
print("완료 — v3.4")
