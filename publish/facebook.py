"""Dang Reels len Facebook Page (3 buoc: start -> rupload -> finish)."""
from __future__ import annotations
import os, time
from pathlib import Path
import requests

API = "https://graph.facebook.com/v21.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v21.0"


def upload(video: Path, caption: str) -> dict:
    page_id = os.environ["FB_PAGE_ID"]
    token = os.environ["FB_PAGE_TOKEN"]

    r = requests.post(f"{API}/{page_id}/video_reels",
                      data={"upload_phase": "start", "access_token": token},
                      timeout=60)
    r.raise_for_status()
    video_id = r.json()["video_id"]

    size = video.stat().st_size
    with video.open("rb") as fh:
        r = requests.post(f"{RUPLOAD}/{video_id}",
                          headers={"Authorization": f"OAuth {token}",
                                   "offset": "0", "file_size": str(size)},
                          data=fh, timeout=900)
    r.raise_for_status()

    r = requests.post(f"{API}/{page_id}/video_reels",
                      data={"upload_phase": "finish", "video_id": video_id,
                            "video_state": "PUBLISHED", "description": caption,
                            "access_token": token}, timeout=120)
    r.raise_for_status()

    # Meta xu ly bat dong bo; doi trang thai mot chut de bao cao cho trung thuc.
    for _ in range(10):
        time.sleep(6)
        s = requests.get(f"{API}/{video_id}",
                         params={"fields": "status", "access_token": token},
                         timeout=30).json()
        if s.get("status", {}).get("video_status") in ("ready", "error"):
            break
    return {"platform": "facebook", "id": video_id,
            "url": f"https://facebook.com/reel/{video_id}",
            "status": s.get("status", {}).get("video_status", "unknown")}
