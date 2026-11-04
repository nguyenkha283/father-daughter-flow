"""
Dang video native len X.

QUAN TRONG VE TIEN: post co chua URL bi tinh ~$0.20/request, post thuong
~$0.015. Chenh hon 13 lan. Nen bai goc KHONG duoc chua link — link di vao reply
hoac bo han. Ham nay chan cung truong hop do.
"""
from __future__ import annotations
import os, re, time
from pathlib import Path
import requests
from requests_oauthlib import OAuth1

UPLOAD = "https://upload.twitter.com/1.1/media/upload.json"
TWEETS = "https://api.x.com/2/tweets"
CHUNK = 4 * 1024 * 1024
URL_RE = re.compile(r"https?://|www\.", re.I)


def _auth() -> OAuth1:
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def _upload_media(video: Path, auth) -> str:
    size = video.stat().st_size
    r = requests.post(UPLOAD, auth=auth, timeout=60, data={
        "command": "INIT", "media_type": "video/mp4",
        "total_bytes": size, "media_category": "tweet_video"})
    r.raise_for_status()
    mid = r.json()["media_id_string"]

    with video.open("rb") as fh:
        for i in range(0, (size + CHUNK - 1) // CHUNK):
            requests.post(UPLOAD, auth=auth, timeout=300,
                          data={"command": "APPEND", "media_id": mid,
                                "segment_index": i},
                          files={"media": fh.read(CHUNK)}).raise_for_status()

    r = requests.post(UPLOAD, auth=auth, timeout=60,
                      data={"command": "FINALIZE", "media_id": mid})
    r.raise_for_status()

    info = r.json().get("processing_info")
    while info and info.get("state") in ("pending", "in_progress"):
        time.sleep(info.get("check_after_secs", 5))
        info = requests.get(UPLOAD, auth=auth, timeout=30,
                            params={"command": "STATUS", "media_id": mid}
                            ).json().get("processing_info")
    if info and info.get("state") == "failed":
        raise RuntimeError(f"X xu ly video that bai: {info}")
    return mid


def upload(video: Path, text: str) -> dict:
    if URL_RE.search(text):
        raise ValueError(
            "Bai X chua URL -> bi tinh ~$0.20 thay vi ~$0.015. "
            "Bo link khoi bai goc, dat vao reply neu can.")
    auth = _auth()
    mid = _upload_media(video, auth)
    r = requests.post(TWEETS, auth=auth, timeout=60,
                      json={"text": text[:280], "media": {"media_ids": [mid]}})
    r.raise_for_status()
    tid = r.json()["data"]["id"]
    return {"platform": "x", "id": tid, "url": f"https://x.com/i/status/{tid}"}
