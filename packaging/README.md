# packaging/

빌드와 배포에 쓰는 파일들.

| 파일 | 하는 일 |
|---|---|
| `build_macos.sh` | macOS 앱 번들(.app) 빌드 |
| `build_windows.bat` | 윈도우 단일 실행 파일(.exe) 빌드 |
| `konvin_macos.spec` | macOS PyInstaller 설정 (번들 버전이 여기 하드코딩되어 있음) |
| `konvin.spec` | 윈도우 PyInstaller 설정 |
| `PKGBUILD` | 아치 리눅스 패키지 정의 |
| `vendor/` | 함께 묶는 yt-dlp 바이너리 (빌드 스크립트가 받아온다) |

두 빌드 스크립트 모두 빌드 직전에 `scripts/smoke_test.py` 를 돌리고,
실패하면 빌드를 멈춘다.

## 버전 올릴 때

`scripts/konvin.py` 의 `VERSION` 과 `konvin_macos.spec` 의 버전 세 곳
(`version=`, `CFBundleShortVersionString`, `CFBundleVersion`)을 같이
고쳐야 한다. 윈도우 spec 에는 버전이 들어있지 않다.

## 아이콘 바꿀 때

`assets/konvin.png` 를 교체한 뒤 기존 변환본을 **반드시 지워야** 한다.
빌드 스크립트가 이미 있으면 건너뛰기 때문이다.

```bash
rm -f assets/konvin.icns      # macOS
del assets\konvin.ico         # 윈도우
```

PNG 는 1024×1024, 스퀘어클이 824px 로 중앙 정렬된 macOS 아이콘 그리드를
따른다. macOS 는 .icns 아트워크를 마스크 없이 그대로 그리기 때문에
모양과 여백을 그림 자체가 갖고 있어야 한다.

## 없어진 패치 스크립트

예전에는 `patch_bundle.py`(v2.8→v2.9), `patch_cleanup.py`(v2.9→v3.0),
`patch_v34.py`(v3.0→v3.4) 처럼 `scripts/konvin.py` 를 일괄 치환하는
스크립트로 버전을 올렸다. 전부 한 번 쓰고 끝나는 물건이라 지웠다.
필요하면 git 이력에서 꺼내 볼 수 있다.

이 방식은 코드 블록을 통째로 지우면서 관련 문자열은 남겨두기 쉬웠고,
실제로 v3.4 에서 그런 잔재가 남아 혼란을 일으켰다. 이후로는 소스를
직접 고치고 `smoke_test.py` 로 확인한다.
