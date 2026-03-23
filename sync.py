import os
import json
import subprocess

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import pickle

TIKTOK_USER = "realjoesema"

PROCESSED_FILE = "processed.json"
DOWNLOAD_DIR = "videos"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def generate_token_locally():
    """
    Run this function ONLY on your local machine to generate token.pickle.
    This will open a browser popup for Google login.

    After running once, upload token.pickle to your server.
    """

    flow = InstalledAppFlow.from_client_secrets_file(
        "./client_secret.json",
        SCOPES
    )

    credentials = flow.run_local_server(
        port=0,
        access_type='offline',   # ensures refresh token
        prompt='consent'         # forces refresh token creation
    )

    with open("./token.pickle", "wb") as token:
        pickle.dump(credentials, token)

    print("✅ token.pickle generated successfully")
    print("Refresh token:", credentials.refresh_token)

def get_authenticated_service():
    """
    Server-safe authentication:
    - Loads token.pickle
    - Refreshes token automatically
    - NEVER opens browser / popup
    """

    if not os.path.exists("./token.pickle"):
        raise Exception("❌ token.pickle not found. Run generate_token_locally() first.")

    with open("./token.pickle", "rb") as token:
        credentials = pickle.load(token)

    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        print("🔄 Refreshing access token...")
        credentials.refresh(Request())

        with open("./token.pickle", "wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)


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


def upload_to_youtube(filepath, metadata):

    youtube = get_authenticated_service()

    title = metadata["title"][:100]  # YouTube title limit
    description = metadata["description"]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": metadata["tags"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(filepath)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = request.execute()

    print("Uploaded:", response["id"])


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
        "uploader": data.get("uploader", ""),
        "tags": data.get("tags", [])
    }

def main():

    # # RUN THIS LOCALLY ONCE TO GENERATE TOKEN.PICKLE FOR YOUTUBE UPLOADS
    # # AFTER GENERATING -> UPLOAD TOKEN.PICKLE TO SERVER
    # generate_token_locally()
    # return

    processed = load_processed()

    video_ids = get_tiktok_video_ids()

    for vid in video_ids:

        if vid not in processed:

            print("New video detected:", vid)

            metadata = get_tiktok_metadata(vid)

            file_path = download_video(vid)

            try:
                upload_to_youtube(file_path, metadata)
            except Exception as e:
                print("Upload failed:", e)

            # cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                print("Deleted local file:", file_path)

            processed.add(vid)

    save_processed(processed)

    print("Done")


if __name__ == "__main__":
    main()