# packaging/

빌드와 배포에 쓰는 파일들. (리눅스 전용)

| 파일 | 하는 일 |
|---|---|
| `PKGBUILD` | 아치 리눅스 패키지 정의 |

리눅스는 소스 + 루트의 `install.sh` 로 설치한다. 별도 빌드 바이너리는
만들지 않는다. (macOS·윈도우 지원은 중단했다.)

## 릴리스

리포 루트의 `release.sh` 가 버전을 올리고 태그를 밀면
`.github/workflows/release.yml` 이 태그로 GitHub 릴리스를 만든다.
첨부 바이너리는 없고 릴리스 노트만 붙는다.

```bash
./release.sh 4.7 notes.md
```

릴리스 설명은 `docs/release-notes/v<버전>.md` 를 쓴다. 없으면 태그
이름만 적힌다.

`check.yml` 은 푸시·PR 마다 리눅스에서 스모크 테스트만 돌린다.

## 버전 올릴 때

`release.sh` 가 두 곳을 한꺼번에 바꾸고, 바뀐 개수가 2가 아니면 멈춘다.
손으로 고칠 때는 `scripts/konvin.py` 의 `VERSION` 과 `PKGBUILD` 의
`pkgver` 를 같이 고친다.

## 아이콘 바꿀 때

`assets/konvin.png` 를 교체하면 된다. 앱은 이 PNG 를 직접 쓴다.
