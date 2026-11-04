#!/usr/bin/env python3
"""
Lay credential cho pipeline. CHAY TREN MAY CA NHAN CUA BAN, khong chay o dau khac.

    python scripts/get_tokens.py youtube     # mo trinh duyet, lay refresh token
    python scripts/get_tokens.py facebook    # doi token ngan han -> page token dai han
    python scripts/get_tokens.py verify      # goi thu ca 3 nen tang
    python scripts/get_tokens.py secrets     # in lenh nap vao GitHub Secrets

Token in ra man hinh. Dung paste vao chat, dung commit. Nap thang vao
GitHub Secrets roi xoa khoi lich su terminal.
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"

# Xin ca 3 scope ngay tu dau: upload de dang, 2 scope analytics de sau nay
# metrics.py dung duoc ma khong phai bat ban dong y lai lan nua.
YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
FB_API = "https://graph.facebook.com/v21.0"

SECRET_KEYS = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN",
               "FB_PAGE_ID", "FB_PAGE_TOKEN",
               "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]


# --------------------------------------------------------------------------- #
def load_env() -> dict[str, str]:
    env = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return {**env, **{k: v for k, v in os.environ.items() if k in SECRET_KEYS}}


def write_env(updates: dict[str, str]) -> None:
    """Cap nhat .env, giu nguyen cac dong khac."""
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    seen = set()
    out = []
    for line in lines:
        k = line.split("=", 1)[0].strip() if "=" in line else None
        if k in updates:
            out.append(f"{k}={updates[k]}"); seen.add(k)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\n-> da ghi {', '.join(updates)} vao {ENV}")


# --------------------------------------------------------------------------- #
def cmd_youtube(a) -> int:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Thieu thu vien. Chay:\n"
              "  pip install google-auth-oauthlib google-api-python-client")
        return 1

    cid = a.client_id or input("YT_CLIENT_ID: ").strip()
    sec = a.client_secret or input("YT_CLIENT_SECRET: ").strip()
    if not (cid and sec):
        print("Thieu client id/secret.\n"
              "Lay o: Google Cloud Console > APIs & Services > Credentials\n"
              "  > Create credentials > OAuth client ID > Desktop app")
        return 1

    cfg = {"installed": {
        "client_id": cid, "client_secret": sec,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]}}

    print("\nTrinh duyet se mo ra. Dang nhap bang tai khoan SO HUU KENH.")
    creds = InstalledAppFlow.from_client_config(cfg, YT_SCOPES).run_local_server(
        port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        print("\nKhong nhan duoc refresh token. Vao "
              "https://myaccount.google.com/permissions go quyen cua app nay "
              "roi chay lai.")
        return 1

    print("\n" + "=" * 62)
    print("YT_REFRESH_TOKEN =", creds.refresh_token)
    print("=" * 62)
    print("scope:", " ".join(creds.scopes or []))
    if a.write:
        write_env({"YT_CLIENT_ID": cid, "YT_CLIENT_SECRET": sec,
                   "YT_REFRESH_TOKEN": creds.refresh_token})
    return 0


def cmd_facebook(a) -> int:
    import requests
    app_id = a.app_id or input("FB App ID: ").strip()
    app_sec = a.app_secret or input("FB App Secret: ").strip()
    short = a.short_token or input(
        "Short-lived USER token (Graph API Explorer, chon quyen "
        "pages_show_list + pages_read_engagement + pages_manage_posts): ").strip()

    r = requests.get(f"{FB_API}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_sec, "fb_exchange_token": short})
    if r.status_code != 200:
        print("Doi token that bai:", r.text[:400]); return 1
    long_user = r.json()["access_token"]
    print("\n-> da co long-lived user token")

    r = requests.get(f"{FB_API}/me/accounts", timeout=30,
                     params={"access_token": long_user,
                             "fields": "id,name,access_token"})
    if r.status_code != 200:
        print("Khong lay duoc danh sach Page:", r.text[:400]); return 1
    pages = r.json().get("data", [])
    if not pages:
        print("Tai khoan nay khong quan tri Page nao."); return 1

    for i, p in enumerate(pages, 1):
        print(f"  [{i}] {p['name']}  (id {p['id']})")
    idx = 0 if len(pages) == 1 else int(input("Chon Page so: ")) - 1
    page = pages[idx]

    print("\n" + "=" * 62)
    print("FB_PAGE_ID    =", page["id"])
    print("FB_PAGE_TOKEN =", page["access_token"])
    print("=" * 62)
    print("Page token tu long-lived user token thuong khong het han, nhung se\n"
          "chet neu ban doi mat khau hoac go quyen cua app.")
    if a.write:
        write_env({"FB_PAGE_ID": page["id"],
                   "FB_PAGE_TOKEN": page["access_token"]})
    return 0


def cmd_verify(a) -> int:
    import requests
    env = load_env()
    rows = []

    # --- YouTube ---
    if all(env.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            c = Credentials(token=None, refresh_token=env["YT_REFRESH_TOKEN"],
                            client_id=env["YT_CLIENT_ID"],
                            client_secret=env["YT_CLIENT_SECRET"],
                            token_uri="https://oauth2.googleapis.com/token",
                            scopes=YT_SCOPES)
            yt = build("youtube", "v3", credentials=c, cache_discovery=False)
            ch = yt.channels().list(part="snippet,statistics", mine=True).execute()
            it = ch["items"][0]
            rows.append(("youtube", "OK", f"{it['snippet']['title']} · "
                         f"{it['statistics'].get('subscriberCount','?')} sub"))
        except Exception as e:
            rows.append(("youtube", "LOI", str(e)[:150]))
    else:
        rows.append(("youtube", "-", "chua cau hinh"))

    # --- Facebook ---
    if env.get("FB_PAGE_ID") and env.get("FB_PAGE_TOKEN"):
        r = requests.get(f"{FB_API}/{env['FB_PAGE_ID']}", timeout=30,
                         params={"fields": "name,fan_count",
                                 "access_token": env["FB_PAGE_TOKEN"]})
        d = r.json()
        rows.append(("facebook", "OK" if r.status_code == 200 else "LOI",
                     f"{d.get('name')} · {d.get('fan_count','?')} follower"
                     if r.status_code == 200 else str(d)[:150]))
    else:
        rows.append(("facebook", "-", "chua cau hinh"))

    # --- X ---
    if all(env.get(k) for k in ("X_API_KEY", "X_API_SECRET",
                                "X_ACCESS_TOKEN", "X_ACCESS_SECRET")):
        try:
            from requests_oauthlib import OAuth1
            r = requests.get("https://api.x.com/2/users/me", timeout=30,
                             auth=OAuth1(env["X_API_KEY"], env["X_API_SECRET"],
                                         env["X_ACCESS_TOKEN"], env["X_ACCESS_SECRET"]))
            d = r.json()
            rows.append(("x", "OK" if r.status_code == 200 else "LOI",
                         f"@{d['data']['username']}" if r.status_code == 200
                         else str(d)[:150]))
        except Exception as e:
            rows.append(("x", "LOI", str(e)[:150]))
    else:
        rows.append(("x", "-", "chua cau hinh"))

    print()
    for name, st, detail in rows:
        print(f"  {st:4s} {name:10s} {detail}")
    bad = [r for r in rows if r[1] == "LOI"]
    ok = [r for r in rows if r[1] == "OK"]
    if bad:
        msg = f"{len(bad)} nen tang loi"
    elif not ok:
        msg = "chua cau hinh nen tang nao — chay 'youtube' va 'facebook' truoc"
    elif len(ok) < len(rows):
        msg = f"{len(ok)}/{len(rows)} nen tang OK, con lai chua cau hinh"
    else:
        msg = "tat ca OK"
    print("\n=> " + msg)
    return 1 if bad else 0


def cmd_secrets(a) -> int:
    env = load_env()
    missing = [k for k in SECRET_KEYS if not env.get(k)]
    print("# Chay tung lenh de nap vao GitHub Secrets.")
    print(f"# Repo: {a.repo}\n")
    for k in SECRET_KEYS:
        v = env.get(k)
        if v:
            print(f'gh secret set {k} --repo {a.repo} --body "{v}"')
        else:
            print(f"# {k}: CHUA CO")
    print(f'\n# Bien thuong (khong phai secret), doi sang public khi audit xong:')
    print(f'gh variable set YT_PRIVACY --repo {a.repo} --body "private"')
    if missing:
        print(f"\n# Con thieu {len(missing)}: {', '.join(missing)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    y = sub.add_parser("youtube"); y.set_defaults(func=cmd_youtube)
    y.add_argument("--client-id"); y.add_argument("--client-secret")
    y.add_argument("--write", action="store_true", help="ghi thang vao .env")

    f = sub.add_parser("facebook"); f.set_defaults(func=cmd_facebook)
    f.add_argument("--app-id"); f.add_argument("--app-secret")
    f.add_argument("--short-token")
    f.add_argument("--write", action="store_true")

    sub.add_parser("verify").set_defaults(func=cmd_verify)

    s = sub.add_parser("secrets"); s.set_defaults(func=cmd_secrets)
    s.add_argument("--repo", default="nguyenkha283/father-daughter-flow")

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
