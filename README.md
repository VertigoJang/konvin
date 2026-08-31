<div align="center">

<img src="assets/konvin.png" width="128" alt="Konvin">

# Konvin

**유튜브 영상을 클릭휠 아이팟에서 볼 수 있게 바꿔 줍니다.**

*Turns YouTube videos into something a click-wheel iPod can play.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<img src="assets/screenshot.png" width="700" alt="Konvin">

</div>

---

## 무엇을 하는 프로그램인가요

주소를 붙여 넣고 가지고 있는 아이팟 세대를 고르면, 영상을 받아서 그 기기가
재생할 수 있는 형식으로 바꿔 줍니다. 해상도·코덱·비트레이트를 매번 맞출 필요
없이 버튼 하나로 끝납니다.

## 지원 기기

영상 재생이 되는 클릭휠 아이팟 세 세대를 모두 지원합니다. 세대를 고르면 나머지
설정은 자동으로 맞춰집니다.

| 세대 | 해상도 | H.264 Level | 영상 비트레이트 상한 |
|---|---|---|---|
| 5세대 (2005) | 320×240 | 1.3 | 768 kbps |
| 5.5세대 (2006) | 640×480 | 2.0 | 1.5 Mbps |
| 6·7세대 Classic (2007~) | 640×480 | 3.0 | 2.5 Mbps |

액정은 세 세대 모두 2.5인치 320×240 입니다. 6·7세대에서 640×480 으로 만들면
기기 화면에서는 축소되어 보이지만, TV 출력으로 볼 때 차이가 납니다.

> 어느 세대인지 모르겠다면 **5세대**를 고르세요. 가장 낮은 사양이라 뒷세대에서도
> 그대로 재생됩니다.

> 상한을 꽉 채우면 배터리 소모와 발열이 심해집니다. 오래 볼 생각이라면 **보통**을
> 권합니다.

## 출력 형식

| 항목 | 값 |
|---|---|
| 컨테이너 | MP4 (`.m4v`) |
| 영상 | H.264 Constrained Baseline (또는 MPEG-4 Simple Profile) |
| 프레임 | 30 fps |
| 소리 | AAC-LC, 44.1kHz, 스테레오 |
| 소리 비트레이트 | 96k / 128k / 160k 중 선택 |

영상과 소리 품질은 따로 고를 수 있습니다. 음악 위주의 영상이라면 영상을 낮게,
소리를 높게 두는 식으로 조합하면 됩니다.

## 주요 기능

- 아이팟 세대를 고르면 인코딩 설정이 자동으로 맞춰짐
- 영상과 소리 품질을 따로 선택
- 단일 영상과 재생목록 모두 지원 (재생목록은 파일 이름에 순번이 붙습니다)
- 여러 주소를 대기열에 넣고 한 번에 처리
- 이미 받은 영상은 자동으로 건너뜀
- 진행률과 남은 시간 표시
- 중단해도 망가진 파일이 남지 않고, 이어서 변환 가능
- 작업이 끝나면 시스템 알림
- 쌓인 파일을 폴더별로 정리하는 기능
- 화면 비율 처리 선택 (레터박스 / 원본 비율 유지)
- 한국어 / English
- Linux · Windows 지원 (macOS 는 확인 중)

## 설치

### Linux

```bash
git clone https://github.com/VertigoJang/konvin.git
cd konvin
./install.sh
konvin
```

앱 메뉴에서 **Konvin** 을 찾아 실행해도 됩니다.
Python 가상 환경과 필요한 패키지는 처음 실행할 때 알아서 준비됩니다.
관리자 권한은 필요하지 않으며, 모든 파일은 홈 디렉터리 안에만 설치됩니다.

제거하려면 `./install.sh --remove` 를 실행하세요.

### Windows

Git 과 Python 이 필요합니다. 없다면 먼저 설치하세요.

```powershell
winget install Git.Git
winget install Python.Python.3.12
```

그다음 명령 프롬프트(cmd)에서:

```
cd %USERPROFILE%
git clone https://github.com/VertigoJang/konvin.git konvin-src
cd konvin-src
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-gui.txt
python scripts\konvin.py
```

> Python 3.10 이상이 필요합니다.

### ffmpeg

영상 변환은 **ffmpeg** 라는 별도 프로그램이 담당합니다. Konvin 에는 포함되어 있지
않으며, 컴퓨터에 없으면 처음 실행할 때 안내 창이 뜹니다. 두 가지 방법 중 하나를
고르면 됩니다.

**패키지 관리자로 설치 (권장)**

```bash
sudo pacman -S ffmpeg          # Arch, Manjaro
sudo apt install ffmpeg        # Debian, Ubuntu, Mint
sudo dnf install ffmpeg        # Fedora
sudo zypper install ffmpeg     # openSUSE
brew install ffmpeg            # macOS
winget install Gyan.FFmpeg     # Windows
```

**안내 창에서 직접 내려받기**

안내 창의 "지금 내려받기" 를 누르면 정적 빌드를 받아 작업 폴더의 `bin` 아래에
저장합니다. 시스템에는 아무것도 설치하지 않습니다.

## 설정

**설정 › 인코딩** 에서 두 가지를 바꿀 수 있습니다.

**코덱** — 기본은 H.264 입니다. 같은 용량에서 화질이 더 좋습니다. 어떤 이유로
영상이 재생되지 않을 때만 MPEG-4 Simple Profile 을 시도해 보세요.

**화면 비율** — 아이팟 화면은 4:3 입니다. 검은 띠를 넣어 4:3 에 맞추면 어떤
기기에서도 안정적으로 재생되고, 원본 비율을 그대로 두면 파일이 조금 작아집니다.

## 파일이 저장되는 곳

| 운영체제 | 위치 |
|---|---|
| Linux, macOS | `~/Konvin` |
| Windows | `%USERPROFILE%\Documents\Konvin` |

| 폴더 | 내용 |
|---|---|
| `tempv` | 단일 영상으로 받은 원본 |
| `playlistv` | 재생목록으로 받은 원본 |
| `changedv` | **변환이 끝난 영상 — 아이팟에 넣을 파일** |
| `archivev` | 변환 후 보관된 원본 |
| `bin` | 직접 내려받은 ffmpeg |

`download_archive.txt` 에 이미 받은 영상의 목록이, `config.json` 에 설정이 저장됩니다.
프로그램의 **설정 › 정리** 탭에서 쌓인 파일을 지울 수 있습니다.

## 버그 신고

[GitHub Issues](https://github.com/VertigoJang/konvin/issues)에 남겨 주세요.
프로그램의 **로그 보기** 를 눌러서 나오는 내용을 함께 보내 주시면 원인을 찾는 데 큰 도움이 됩니다.

## 후원

마음에 드셨다면 개발자에게 커피 한 잔, 맥주 한 잔 어떠세요?

[☕ Buy me a coffee](https://buymeacoffee.com/iputaspellonyou)

## 라이선스

MIT License — 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.

Copyright (c) 2026 장현기 (VertigoJang)

이 프로그램은 [yt-dlp](https://github.com/yt-dlp/yt-dlp)와 [ffmpeg](https://ffmpeg.org/)를
사용합니다. 각각의 라이선스는 해당 프로젝트를 따릅니다. ffmpeg 바이너리는 Konvin 에
포함되어 있지 않으며, 사용자가 직접 설치하거나 내려받습니다.

Konvin은 Apple Inc.와 관련이 없으며, 승인받거나 후원받지 않았습니다.
iPod은 Apple Inc.의 등록 상표입니다.

---

<div align="center">

## English

</div>

**Konvin** downloads a YouTube video and converts it into something a click-wheel
iPod can actually play. Pick your generation and the rest is set for you — no
need to work out the right resolution, codec level or bitrate yourself.

### Supported devices

| Generation | Resolution | H.264 Level | Max video bitrate |
|---|---|---|---|
| 5th (2005) | 320×240 | 1.3 | 768 kbps |
| 5.5th (2006) | 640×480 | 2.0 | 1.5 Mbps |
| 6th/7th Classic (2007–) | 640×480 | 3.0 | 2.5 Mbps |

All three have the same 2.5-inch 320×240 screen; the higher resolutions matter
for TV output. If you're unsure which you have, pick the 5th generation — its
files play on every later model. Running at the bitrate ceiling drains the
battery, so Medium is the better everyday choice.

Output is MP4 (`.m4v`) with H.264 Constrained Baseline video at 30 fps and
AAC-LC audio at 44.1kHz stereo. Video and audio quality are chosen separately,
so you can pair low video with high audio for a music video, or the other way
round. MPEG-4 Simple Profile is available as a compatibility fallback.

### Features

- Encoding settings follow the iPod generation you select
- Single videos and playlists (playlist files get a numeric prefix)
- Queue several URLs and process them in one go
- Already-downloaded videos are skipped automatically
- Progress bar with estimated time remaining
- Stopping never leaves a broken file behind; conversion can be resumed
- System notification when the batch finishes
- Built-in cleanup for accumulated files
- Letterbox or original aspect ratio
- Korean / English interface
- Linux and Windows (macOS untested so far)

### Install

**Linux**

```bash
git clone https://github.com/VertigoJang/konvin.git
cd konvin
./install.sh
konvin
```

**Windows** — with Git and Python 3.10+ installed:

```
cd %USERPROFILE%
git clone https://github.com/VertigoJang/konvin.git konvin-src
cd konvin-src
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-gui.txt
python scripts\konvin.py
```

### ffmpeg

Conversion is done by **ffmpeg**, a separate program that is not bundled with
Konvin. If it isn't on your computer, a dialog on first run offers two options:
install it through your package manager (recommended), or download a static
build into Konvin's own `bin` folder without touching your system.

### Where files go

`~/Konvin` on Linux and macOS, `Documents\Konvin` on Windows. Converted videos —
the ones you copy to your iPod — end up in `changedv`.

### Bugs

Please open an issue on [GitHub](https://github.com/VertigoJang/konvin/issues).
Including the output from **Show log** helps a great deal.

### License

MIT. Copyright (c) 2026 장현기 (VertigoJang).

Konvin is not affiliated with, endorsed by, or sponsored by Apple Inc.
iPod is a registered trademark of Apple Inc.
