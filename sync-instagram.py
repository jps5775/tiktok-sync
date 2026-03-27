import os
import json
import subprocess
import time
import requests
import boto3

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ==============================
# CONFIG
# ==============================

TIKTOK_USER = "realjoesema"

PROCESSED_FILE = "processed_ig.json"
DOWNLOAD_DIR = "videos-ig"

BUCKET_NAME = os.getenv("S3_BUCKET")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("REGION_NAME")
)
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ==============================
# HELPERS
# ==============================

def upload_to_s3(filepath, video_id):
    key = f"{video_id}.mp4"

    s3.upload_file(
        filepath,
        BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": "video/mp4"}
    )

    url = f"https://{BUCKET_NAME}.s3.{os.getenv('REGION_NAME')}.amazonaws.com/{key}"

    return key, url


def delete_from_s3(key):
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    print("Deleted from S3:", key)

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
    for entry in data.get("entries", []):
        if entry and "id" in entry:
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


def get_tiktok_metadata(video_id):
    url = f"https://www.tiktok.com/@{TIKTOK_USER}/video/{video_id}"

    result = subprocess.check_output([
        "yt-dlp",
        "-J",
        url
    ])

    data = json.loads(result)

    return {
        "title": data.get("description", ""),
        "description": data.get("description", ""),
        "tags": data.get("tags", [])
    }

# ==============================
# INSTAGRAM UPLOAD
# ==============================

def upload_to_instagram(video_url, caption):
    print("Uploading to Instagram...")

    # Step 1: Create media container
    res = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={
            "video_url": video_url,
            "caption": caption[:2200],
            "media_type": "REELS",
            "access_token": ACCESS_TOKEN
        }
    )

    data = res.json()

    if "id" not in data:
        print("❌ IG Container Creation Error:", data)
        raise Exception(f"IG container creation failed: {data}")
    else:
        print("✅ IG Container Success:", data)

    creation_id = data["id"]

    # Wait for processing (IMPORTANT)
    print("Waiting for Instagram to process video...")
    time.sleep(30)

    # Step 2: Publish
    res = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN
        }
    )

    response_data = res.json()

    if "id" not in response_data:
        print("❌ IG Publish Error:", response_data)
        raise Exception(f"IG publish failed: {response_data}")
    else:
        print("✅ IG Upload Success:", response_data)


# ==============================
# MAIN
# ==============================

def main():

    print("🚀 Starting Instagram sync...")

    processed = load_processed()
    video_ids = get_tiktok_video_ids()

    for vid in video_ids:

        if vid in processed:
            continue

        print(f"\n🎬 New video detected: {vid}")

        metadata = get_tiktok_metadata(vid)
        file_path = download_video(vid)

        success = False
        key = None

        try:
            # Upload to S3
            key, video_url = upload_to_s3(file_path, vid)

            # Retry IG upload
            for attempt in range(3):
                try:
                    print(f"📤 IG upload attempt {attempt+1} for {vid}")
                    upload_to_instagram(video_url, metadata["description"])
                    success = True
                    break
                except Exception as e:
                    print(f"⚠️ Retry {attempt+1} failed for {vid}: {e}")
                    time.sleep(5)

            # Give IG time to fetch video before deleting
            print("⏳ Waiting before cleanup...")
            time.sleep(30)

        except Exception as e:
            print(f"❌ Upload pipeline failed for {vid}: {e}")

        finally:
            # Always delete local file
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🧹 Deleted local file: {file_path}")

            # Delete from S3 if it was uploaded
            if key:
                try:
                    delete_from_s3(key)
                except Exception as e:
                    print(f"⚠️ Failed to delete from S3: {e}")

        # Only mark as processed if IG upload succeeded
        if success:
            processed.add(vid)
            print(f"🎉 Successfully processed video: {vid}")
        else:
            print(f"❌ Skipping marking as processed (will retry later): {vid}")

    save_processed(processed)

    print("\n✅ Instagram sync complete")


if __name__ == "__main__":
    main()