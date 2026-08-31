# -*- mode: python ; coding: utf-8 -*-
#
# Konvin — Windows 단일 실행 파일 빌드 설정
#
# 리포 루트에서 실행:
#     pyinstaller packaging/konvin.spec
#
# 미리 준비되어 있어야 하는 것:
#     assets/konvin.ico          아이콘
#     packaging/vendor/yt-dlp.exe  yt-dlp 공식 독립 실행 파일
#
# build_windows.bat 이 이 둘을 자동으로 준비한다.

from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "assets" / "konvin.png"), "assets"),
    (str(ROOT / "LICENSE"), "."),
]

binaries = []

# yt-dlp 는 함께 묶는다. ffmpeg 는 GPL 이라 넣지 않고, 없으면 프로그램이
# 설치 방법을 안내한다.
ytdlp = ROOT / "packaging" / "vendor" / "yt-dlp.exe"

if ytdlp.exists():
    binaries.append((str(ytdlp), "."))

analysis = Analysis(
    [str(ROOT / "scripts" / "konvin.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 쓰지 않는 Qt 모듈을 빼서 용량을 줄인다
    excludes=[
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNfc",
        "PySide6.QtOpenGL",
        "PySide6.QtPdf",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "tkinter",
        "matplotlib",
        "numpy",
        "PIL",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="Konvin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "konvin.ico"),
)
