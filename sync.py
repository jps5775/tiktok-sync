import os
import json
import subprocess

TIKTOK_USER = "realjoesema"

PROCESSED_FILE = "processed.json"
DOWNLOAD_DIR = "videos"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_processed():
    if not os.path.exists(PROCESSED_FILE):
        return set()

    with open(PROCESSED_FILE, "r") as f:
        return set(json.load(f))


def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)


def get_tiktok_video_ids():

    print("Checking TikTok account...")

    result = subprocess.check_output([
        "yt-dlp",
        "--flat-playlist",
        "-J",
        f"https://www.tiktok.com/@{TIKTOK_USER}"
    ])

    data = json.loads(result)

    ids = []

    for entry in data["entries"]:
        ids.append(entry["id"])

    return ids


def download_video(video_id):

    url = f"https://www.tiktok.com/@{TIKTOK_USER}/video/{video_id}"

    filepath = f"{DOWNLOAD_DIR}/{video_id}.mp4"

    subprocess.run([
        "yt-dlp",
        "-o",
        filepath,
        "-f",
        "mp4",
        url
    ])

    return filepath


def upload_to_youtube(filepath):

    # placeholder
    print("Uploading to YouTube Shorts:", filepath)

    # Use YouTube Data API
    print("Need to implement YouTube upload...")


def main():

    processed = load_processed()

    video_ids = get_tiktok_video_ids()

    for vid in video_ids:

        if vid not in processed:

            print("New video detected:", vid)

            file_path = download_video(vid)

            upload_to_youtube(file_path)

            # cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                print("Deleted local file:", file_path)

            processed.add(vid)

    save_processed(processed)

    print("Done")


if __name__ == "__main__":
    main()