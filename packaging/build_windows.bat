@echo off
rem ============================================
rem  Konvin - Windows 단일 실행 파일 빌드
rem
rem  리포 루트에서 실행:
rem      packaging\build_windows.bat
rem ============================================

setlocal

cd /d "%~dp0.."

if not exist "scripts\konvin.py" (
    echo scripts\konvin.py 를 찾을 수 없습니다.
    echo 리포 루트에서 실행하고 있는지 확인하세요.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo 가상 환경이 없습니다. 먼저 아래를 실행하세요.
    echo     python -m venv .venv
    echo     .venv\Scripts\activate
    echo     pip install -r requirements-gui.txt
    exit /b 1
)

set PY=.venv\Scripts\python.exe

echo.
echo [1/4] 빌드 도구 설치
"%PY%" -m pip install --quiet --upgrade pyinstaller pillow
if errorlevel 1 exit /b 1

echo.
echo [2/4] 아이콘 준비
if exist "assets\konvin.ico" (
    echo     이미 있음, 건너뜀
) else (
    "%PY%" -c "from PIL import Image; Image.open('assets/konvin.png').save('assets/konvin.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if errorlevel 1 exit /b 1
    echo     assets\konvin.ico 생성
)

echo.
echo [3/4] yt-dlp 내려받기
if not exist "packaging\vendor" mkdir "packaging\vendor"

if exist "packaging\vendor\yt-dlp.exe" (
    echo     이미 있음, 건너뜀
    echo     최신판을 쓰려면 packaging\vendor\yt-dlp.exe 를 지우고 다시 실행하세요.
) else (
    echo     github.com/yt-dlp/yt-dlp 에서 받는 중...
    "%PY%" -c "import urllib.request; urllib.request.urlretrieve('https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe', 'packaging/vendor/yt-dlp.exe')"
    if errorlevel 1 (
        echo     내려받기 실패. 직접 받아서 packaging\vendor\yt-dlp.exe 로 두세요.
        exit /b 1
    )
    echo     packaging\vendor\yt-dlp.exe 준비
)

echo.
echo [4/4] 빌드 (몇 분 걸립니다)
"%PY%" -m PyInstaller --noconfirm --clean packaging\konvin.spec
if errorlevel 1 exit /b 1

echo.
echo ============================================
echo  완료: dist\Konvin.exe
echo ============================================
echo.
dir /b dist

endlocal
