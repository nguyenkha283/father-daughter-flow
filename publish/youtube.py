"""Upload YouTube Shorts qua Data API v3 (OAuth refresh token)."""
from __future__ import annotations
import os
from pathlib import Path

# Project chua qua compliance audit thi video BI KHOA private du dat gi di nua.
# Giu mac dinh 'private' de hanh vi that khop voi ky vong, doi audit xong
# thi dat YT_PRIVACY=public.
DEFAULT_PRIVACY = os.environ.get("YT_PRIVACY", "private")


def upload(video: Path, title: str, description: str, tags: list[str],
           privacy: str | None = None, publish_at: str | None = None) -> dict:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    status = {"privacyStatus": privacy or DEFAULT_PRIVACY,
              "selfDeclaredMadeForKids": False}   # muc 9 World Bible
    if publish_at:
        status["publishAt"] = publish_at
        status["privacyStatus"] = "private"       # bat buoc khi hen gio

    req = yt.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title[:100],
                          "description": description[:5000],
                          "tags": tags[:30], "categoryId": "22"},
              "status": status},
        media_body=MediaFileUpload(str(video), chunksize=4 * 1024 * 1024,
                                   resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        prog, resp = req.next_chunk()
        if prog:
            print(f"  youtube {int(prog.progress()*100)}%")
    vid = resp["id"]
    return {"platform": "youtube", "id": vid,
            "url": f"https://youtube.com/shorts/{vid}",
            "privacy": status["privacyStatus"]}
