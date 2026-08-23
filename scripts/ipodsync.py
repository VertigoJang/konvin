#!/usr/bin/env python3

# ============================================
# iPodSync
# Version : v0.5
# Codename: Playlist
# ============================================

import json
import shutil
import subprocess
from pathlib import Path

VERSION  = "v0.5"
CODENAME = "Playlist"

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

# iPod Classic 5G: H.264 Baseline Profile Level 3.0, 320x240, 768kbps ceiling
QUALITY_PROFILES = {
    "low": {
        "label":   "Low     (video 384k / audio  96k)",
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
        "label":   "High    (video 768k / audio 160k)",
        "vb":      "768k",
        "maxrate": "768k",
        "bufsize": "1536k",
        "ab":      "160k",
    },
}

DEFAULT_QUALITY = "medium"


# ============================================
# Config
# ============================================

def load_config():
    config = {"quality": DEFAULT_QUALITY}

    if not CONFIG_FILE.exists():
        return config

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Config load failed ({e}); using defaults.")
        return config

    quality = data.get("quality", DEFAULT_QUALITY)

    if quality in QUALITY_PROFILES:
        config["quality"] = quality

    return config


def save_config(config):
    try:
        CONFIG_FILE.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"Config save failed: {e}")


CONFIG = load_config()


# ============================================
# Download
# ============================================

def build_ytdlp_command(url, dest_dir, is_playlist):
    if is_playlist:
        template = str(dest_dir / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")
    else:
        template = str(dest_dir / "%(title)s [%(id)s].%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "-o", template,
        "--no-overwrites",
        "--trim-filenames", "200",
        "--download-archive", str(ARCHIVE_FILE),
    ]

    if is_playlist:
        # --download-archive: 이미 받은 영상 ID를 기록해 재실행 시 건너뜀
        cmd += [
            "--yes-playlist",
            "--ignore-errors",
        ]
    else:
        cmd += ["--no-playlist"]

    cmd.append(url)
    return cmd


def download_videos(urls, dest_dir, is_playlist=False):
    print()
    print("Downloading...")
    print()

    failed = []

    for url in urls:
        print(f"Downloading: {url}")

        try:
            result = subprocess.run(build_ytdlp_command(url, dest_dir, is_playlist))
        except FileNotFoundError:
            print("yt-dlp not found. Activate the venv, or run: pip install -U yt-dlp")
            return False
        except KeyboardInterrupt:
            print("\nDownload interrupted by user.")
            return False

        if result.returncode != 0:
            print(f"Download failed: {url}")
            failed.append(url)

    if failed:
        print()
        print(f"{len(failed)} download(s) failed.")

    return True


# ============================================
# Convert
# ============================================

def build_ffmpeg_command(source, dest, quality):
    profile = QUALITY_PROFILES[quality]

    return [
        "ffmpeg",
        "-y",
        "-i", str(source),
        "-vf",
        "scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2",
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
        "-f", "mp4",
        str(dest),
    ]


def convert_one(file, quality):
    """Returns: 'converted' | 'skipped' | 'failed'"""

    output = CHANGEDV / f"{file.stem}_iPod.m4v"

    # 완성된 결과물만 skip 대상. 중단된 변환은 .part 로 남으므로 오인되지 않음
    if output.exists():
        print(f"Skipped (already exists): {output.name}")
        return "skipped"

    # 임시 파일에 인코딩한 뒤 성공했을 때만 rename (원자적 교체)
    temp_output = CHANGEDV / f".{file.stem}_iPod.m4v.part"
    temp_output.unlink(missing_ok=True)

    print()
    print("=" * 50)
    print(f"Converting: {file.name}")
    print("QUALITY:", quality)
    print("INPUT  :", file)
    print("OUTPUT :", output)
    print("=" * 50)

    try:
        result = subprocess.run(build_ffmpeg_command(file, temp_output, quality))
    except FileNotFoundError:
        temp_output.unlink(missing_ok=True)
        print("ffmpeg not found. Install it with: sudo pacman -S ffmpeg")
        raise
    except KeyboardInterrupt:
        temp_output.unlink(missing_ok=True)
        print("\nConversion interrupted; partial file removed.")
        raise

    print("RETURN CODE:", result.returncode)

    if result.returncode != 0:
        temp_output.unlink(missing_ok=True)
        print(f"Failed: {file.name}")
        return "failed"

    temp_output.rename(output)
    print(f"Finished: {output.name}")

    archive_dest = ARCHIVEV / file.name

    try:
        shutil.move(str(file), str(archive_dest))
        print(f"Archived: {file.name}")
    except (OSError, shutil.Error) as e:
        print(f"Archive move failed ({e}); source left in place.")

    return "converted"


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


def convert_videos(source_dir, per_video_quality=False):
    print()
    print("Converting...")
    print()

    files = collect_source_files(source_dir)

    if not files:
        print(f"No convertible files in {source_dir}")
        return

    stats = {"converted": 0, "skipped": 0, "failed": 0}

    for file in files:

        if per_video_quality:
            print()
            print(f"Next: {file.name}")
            quality = ask_quality(default=CONFIG["quality"])
        else:
            quality = CONFIG["quality"]

        try:
            status = convert_one(file, quality)
        except KeyboardInterrupt:
            print("Aborted. Re-run 'Convert Existing Files' to resume.")
            break
        except FileNotFoundError:
            break

        stats[status] += 1

    print()
    print("=" * 50)
    print("All conversions completed.")
    print("-" * 50)
    print(f"Converted : {stats['converted']}")
    print(f"Skipped   : {stats['skipped']}")
    print(f"Failed    : {stats['failed']}")
    print("=" * 50)


# ============================================
# Input helpers
# ============================================

def ask_quality(default=DEFAULT_QUALITY):
    keys = list(QUALITY_PROFILES.keys())

    print()
    print("Quality:")

    for i, key in enumerate(keys, start=1):
        mark = " (current)" if key == default else ""
        print(f"  {i}. {QUALITY_PROFILES[key]['label']}{mark}")

    choice = input(f"Select [1-{len(keys)}, Enter = {default}]: ").strip()

    if not choice:
        return default

    if choice.isdigit() and 1 <= int(choice) <= len(keys):
        return keys[int(choice) - 1]

    print(f"Invalid selection; using {default}.")
    return default


def collect_urls(prompt="YouTube URL: "):
    urls = []

    while True:
        url = input(prompt).strip()

        if not url:
            print("URL cannot be empty.")
            continue

        urls.append(url)

        print()
        print(f"Added ({len(urls)})")
        print(url)

        answer = input("\nAdd another URL? (Y/N): ").strip().upper()

        if answer != "Y":
            break

    return urls


def show_queue_and_confirm(urls):
    print()
    print("Download queue:")
    print("-" * 50)

    for i, url in enumerate(urls, start=1):
        print(f"{i}. {url}")

    print("-" * 50)
    print(f"Total URLs: {len(urls)}")
    print(f"Quality   : {CONFIG['quality']}")

    confirm = input("\nStart download? (Y/N): ").strip().upper()
    return confirm == "Y"


# ============================================
# Menu
# ============================================

def menu_download_video():
    urls = collect_urls()

    if not show_queue_and_confirm(urls):
        print("Cancelled.")
        return

    if download_videos(urls, TEMPV, is_playlist=False):
        convert_videos(TEMPV)


def menu_download_playlist():
    urls = collect_urls("Playlist URL: ")

    if not show_queue_and_confirm(urls):
        print("Cancelled.")
        return

    if not download_videos(urls, PLAYLISTV, is_playlist=True):
        return

    answer = input("\nSet quality per video? (Y/N): ").strip().upper()
    convert_videos(PLAYLISTV, per_video_quality=(answer == "Y"))


def menu_convert_existing():
    print()
    print("1. tempv      (single downloads)")
    print("2. playlistv  (playlist downloads)")
    print("3. Both")

    choice = input("Select source [1-3]: ").strip()

    if choice == "1":
        targets = [TEMPV]
    elif choice == "2":
        targets = [PLAYLISTV]
    elif choice == "3":
        targets = [TEMPV, PLAYLISTV]
    else:
        print("Invalid option.")
        return

    for target in targets:
        print()
        print(f"Scanning {target}...")
        convert_videos(target)


def menu_settings():
    while True:
        print()
        print("=" * 50)
        print("Settings")
        print("=" * 50)
        print(f"1. Default quality  : {CONFIG['quality']}")
        print("2. Show paths")
        print("3. Reset download archive")
        print("4. Back")
        print("-" * 50)

        choice = input("Select an option: ").strip()

        if choice == "1":
            CONFIG["quality"] = ask_quality(default=CONFIG["quality"])
            save_config(CONFIG)
            print(f"Default quality set to {CONFIG['quality']}.")

        elif choice == "2":
            print()
            print(f"tempv        : {TEMPV}")
            print(f"playlistv    : {PLAYLISTV}")
            print(f"changedv     : {CHANGEDV}")
            print(f"archivev     : {ARCHIVEV}")
            print(f"archive file : {ARCHIVE_FILE}")
            print(f"config       : {CONFIG_FILE}")

        elif choice == "3":
            if not ARCHIVE_FILE.exists():
                print("No archive file to reset.")
                continue

            confirm = input(
                "Delete the download archive? Previously downloaded "
                "videos will be fetched again. (Y/N): "
            ).strip().upper()

            if confirm == "Y":
                ARCHIVE_FILE.unlink()
                print("Archive reset.")
            else:
                print("Cancelled.")

        elif choice == "4":
            return

        else:
            print("Invalid option. Please choose 1-4.")


def show_menu():
    print()
    print("=" * 50)
    print(f"iPodSync {VERSION} ({CODENAME})")
    print("=" * 50)
    print("1. Download Video")
    print("2. Download Playlist")
    print("3. Convert Existing Files")
    print("4. Settings")
    print("5. Exit")
    print("-" * 50)


def main():
    while True:
        show_menu()

        try:
            choice = input("Select an option: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        try:
            if choice == "1":
                menu_download_video()
            elif choice == "2":
                menu_download_playlist()
            elif choice == "3":
                menu_convert_existing()
            elif choice == "4":
                menu_settings()
            elif choice == "5":
                print("Goodbye.")
                break
            else:
                print("Invalid option. Please choose 1-5.")
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to menu.")


if __name__ == "__main__":
    main()
