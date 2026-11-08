# packaging/

빌드와 배포에 쓰는 파일들.

| 파일 | 하는 일 |
|---|---|
| `build_macos.sh` | macOS 앱 번들(.app) 빌드 — 맥에서 직접 빌드할 때 |
| `build_windows.bat` | 윈도우 단일 실행 파일(.exe) 빌드 — 윈도우에서 직접 빌드할 때 |
| `konvin_macos.spec` | macOS PyInstaller 설정 (번들 버전이 여기 하드코딩되어 있음) |
| `konvin.spec` | 윈도우 PyInstaller 설정 |
| `PKGBUILD` | 아치 리눅스 패키지 정의 |
| `vendor/` | 함께 묶는 yt-dlp 바이너리 (빌드 스크립트가 받아온다) |

두 빌드 스크립트 모두 빌드 직전에 `scripts/smoke_test.py` 를 돌리고,
실패하면 빌드를 멈춘다.

## 릴리스는 GitHub 에서 빌드한다

평소에는 위 스크립트를 직접 돌리지 않는다. 리포 루트의 `release.sh` 가
버전을 올리고 태그를 밀면 `.github/workflows/release.yml` 이
GitHub 러너에서 두 빌드를 돌려 릴리스에 붙인다.

```bash
./release.sh 4.6 notes.md
```

맥도 윈도우 VM 도 필요 없다. 리눅스 노트북 한 대로 끝난다.

워크플로가 쓰는 러너:

| 잡 | 러너 | 결과물 |
|---|---|---|
| `macos` | `macos-15-intel` | `Konvin-<버전>-macos-intel.zip` |
| `windows` | `windows-latest` | `Konvin-<버전>-windows.exe` |

`macos-15-intel` 은 GitHub 이 남겨 둔 마지막 x86_64 맥 러너다(2027년 8월까지).
기본 `macos-latest` 를 쓰면 애플 실리콘 전용 바이너리가 나와서 지금까지
배포한 것과 달라지므로 라벨을 고정해 두었다. 인텔 빌드는 애플 실리콘
맥에서도 로제타로 돌아간다.

러너가 사라지는 날이 오면 `macos-26-intel` 로 올리거나, 애플 실리콘
빌드를 함께 올리면서 `scripts/konvin_update.py` 의 `asset_for_release()`
를 아키텍처까지 보도록 고쳐야 한다. 지금은 첨부 목록에서 처음 만나는
macOS zip 을 고르기 때문에, macOS zip 이 두 개가 되면 예전 버전의 자동
업데이트가 엉뚱한 쪽을 받는다.

릴리스 설명은 `docs/release-notes/v<버전>.md` 를 쓴다. 없으면 태그
이름만 적힌다.

`check.yml` 은 푸시·PR 마다 리눅스에서 스모크 테스트만 돌린다.
릴리스 때 처음 깨지는 것보다 여기서 먼저 걸리는 쪽이 낫다.

## 버전 올릴 때

`release.sh` 가 다섯 곳을 한꺼번에 바꾸고, 바뀐 개수가 5가 아니면
멈춘다. 워크플로도 태그와 코드의 버전이 맞는지 다시 확인한다.

손으로 고칠 때는 `scripts/konvin.py` 의 `VERSION`, `konvin_macos.spec`
의 세 곳(`version=`, `CFBundleShortVersionString`, `CFBundleVersion`),
`PKGBUILD` 의 `pkgver` 를 같이 고친다. 윈도우 spec 에는 버전이
들어있지 않다.

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
