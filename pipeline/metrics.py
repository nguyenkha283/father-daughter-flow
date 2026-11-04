#!/usr/bin/env python3
"""
Keo so lieu YouTube ve, doi chieu voi dac diem shotlist, de lan sau viet brief
tot hon.

    python -m pipeline.metrics ingest      # quet publish.json, map video <-> job
    python -m pipeline.metrics fetch       # goi YouTube Analytics API
    python -m pipeline.metrics report      # phan tich -> markdown cho Claude doc

Day moi la cho quyet dinh viral. Tu dong hoa chi mang lai PHAN PHOI; cai quyet
dinh video co duoc xem het hay khong la 1.5 giay dau va nhip cam xuc — tuc la
stage brief, khong phai stage render.
"""
from __future__ import annotations

import argparse, json, os, sqlite3, sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import schema  # noqa: E402

DB = ROOT / "metrics.sqlite"
MIN_N = 10          # duoi nguong nay moi ket luan deu la doan mo

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY, job_id TEXT, title TEXT, published_at TEXT);
CREATE TABLE IF NOT EXISTS features (
  job_id TEXT PRIMARY KEY, n_shots INT, duration REAL, parallax_share REAL,
  n_i2v INT, hook_lane TEXT, hook_dur REAL, rest_dur REAL, n_sets INT,
  n_motifs INT, season TEXT, time_of_day TEXT, has_mother INT);
CREATE TABLE IF NOT EXISTS metrics (
  video_id TEXT, day TEXT, views INT, avg_pct REAL, avg_sec REAL,
  likes INT, shares INT, subs INT, PRIMARY KEY (video_id, day));
"""


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c


# --------------------------------------------------------------------------- #
def features(job: schema.Job) -> dict:
    """Dac diem cua mot video, de doi chieu voi retention."""
    rest = [s for s in job.shots if s.beat in ("rest", "end")]
    chars = {c for s in job.shots for c in s.characters}
    return {
        "job_id": job.id,
        "n_shots": len(job.shots),
        "duration": job.duration,
        "parallax_share": round(job.parallax_share, 3),
        "n_i2v": len(job.i2v_shots),
        "hook_lane": job.shots[0].lane if job.shots else "",
        "hook_dur": job.shots[0].duration if job.shots else 0.0,
        "rest_dur": round(sum(s.duration for s in rest)
                          - max(0, len(rest) - 1) * schema.XFADE, 2),
        "n_sets": len({s.set for s in job.shots}),
        "n_motifs": len(job.motifs),
        "season": job.season,
        "time_of_day": job.time,
        "has_mother": int("mother" in chars),
    }


def cmd_ingest(a) -> int:
    con = db(); n = 0
    for pj in sorted((ROOT / "jobs").glob("*/out/publish.json")):
        data = json.loads(pj.read_text(encoding="utf-8"))
        yt = next((r for r in data.get("results", [])
                   if r.get("platform") == "youtube" and r.get("id")), None)
        if not yt:
            continue
        job_id = data["job"]
        yml = next((y for y in (ROOT / "jobs").glob("*.yaml")
                    if schema.load(y).id == job_id), None)
        if yml is None:
            continue
        job = schema.load(yml)
        f = features(job)
        con.execute("INSERT OR REPLACE INTO videos VALUES (?,?,?,?)",
                    (yt["id"], job_id, job.title, data.get("at", "")))
        con.execute(
            f"INSERT OR REPLACE INTO features VALUES ({','.join('?'*13)})",
            tuple(f.values()))
        n += 1
    con.commit()
    print(f"-> dang ky {n} video")
    return 0


def cmd_fetch(a) -> int:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"])
    ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    con = db()
    ids = [r[0] for r in con.execute("SELECT video_id FROM videos")]
    if not ids:
        print("chua co video nao. Chay 'ingest' truoc."); return 0

    end = date.today()
    start = end - timedelta(days=a.days)
    got = 0
    for i in range(0, len(ids), 50):          # API gioi han do dai filter
        chunk = ids[i:i + 50]
        r = ya.reports().query(
            ids="channel==MINE", startDate=str(start), endDate=str(end),
            metrics=("views,averageViewPercentage,averageViewDuration,"
                     "likes,shares,subscribersGained"),
            dimensions="video", filters="video==" + ",".join(chunk),
            maxResults=200).execute()
        for row in r.get("rows", []):
            con.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,?,?,?,?)",
                        (row[0], str(end), int(row[1]), float(row[2]),
                         float(row[3]), int(row[4]), int(row[5]), int(row[6])))
            got += 1
    con.commit()
    print(f"-> cap nhat {got} video, cua so {a.days} ngay")
    return 0


# --------------------------------------------------------------------------- #
def _split_compare(rows: list[dict], key: str, metric: str) -> dict | None:
    """
    Chia doi theo trung vi roi so trung binh. Voi n nho (7-30 video) thi
    he so tuong quan la vo nghia, so sanh hai nhom trung thuc hon.
    """
    vals = [r[key] for r in rows if r.get(key) is not None]
    if len(set(vals)) < 2:
        return None
    med = sorted(vals)[len(vals) // 2]
    lo = [r[metric] for r in rows if r[key] < med]
    hi = [r[metric] for r in rows if r[key] >= med]
    if len(lo) < 2 or len(hi) < 2:
        return None
    return {"feature": key, "cut": round(med, 3),
            "low_n": len(lo), "low": round(mean(lo), 1),
            "high_n": len(hi), "high": round(mean(hi), 1),
            "delta": round(mean(hi) - mean(lo), 1)}


def _group_compare(rows: list[dict], key: str, metric: str) -> list[dict]:
    g: dict[str, list[float]] = {}
    for r in rows:
        g.setdefault(str(r[key]), []).append(r[metric])
    return sorted(({"value": k, "n": len(v), "avg": round(mean(v), 1)}
                   for k, v in g.items() if len(v) >= 2),
                  key=lambda d: -d["avg"])


def cmd_report(a) -> int:
    con = db(); con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("""
        SELECT v.video_id, v.title, f.*, m.views, m.avg_pct, m.avg_sec,
               m.likes, m.shares, m.subs
        FROM videos v JOIN features f ON f.job_id = v.job_id
        JOIN metrics m ON m.video_id = v.video_id
        WHERE m.day = (SELECT MAX(day) FROM metrics WHERE video_id = v.video_id)
    """)]
    if not rows:
        print("chua co so lieu. Chay 'ingest' roi 'fetch'."); return 0

    M = "avg_pct"      # % xem het la chi so quan trong nhat voi Shorts
    out = [f"# Bao cao retention — {len(rows)} video", ""]
    if len(rows) < MIN_N:
        out += [f"> **Chi co {len(rows)} video.** Duoi {MIN_N} video thi moi",
                "> ket luan duoi day deu la doan mo. Doc de co huong thu,",
                "> dung doi chien luoc vi chung.", ""]

    out += ["## Tong quan", "",
            f"- Luot xem trung binh: **{mean(r['views'] for r in rows):.0f}**",
            f"- % xem het trung binh: **{mean(r['avg_pct'] for r in rows):.1f}%**",
            f"- Sub thu duoc: **{sum(r['subs'] for r in rows)}**", ""]

    best = sorted(rows, key=lambda r: -r[M])[:3]
    worst = sorted(rows, key=lambda r: r[M])[:3]
    out += ["## Ba video giu chan tot nhat", ""]
    out += [f"{i}. **{r['title']}** — {r['avg_pct']:.0f}% · {r['views']} view · "
            f"hook {r['hook_lane']} {r['hook_dur']}s · parallax "
            f"{r['parallax_share']:.0%} · lang {r['rest_dur']}s"
            for i, r in enumerate(best, 1)]
    out += ["", "## Ba video kem nhat", ""]
    out += [f"{i}. **{r['title']}** — {r['avg_pct']:.0f}% · {r['views']} view · "
            f"hook {r['hook_lane']} {r['hook_dur']}s · parallax "
            f"{r['parallax_share']:.0%} · lang {r['rest_dur']}s"
            for i, r in enumerate(worst, 1)]

    out += ["", "## Dac diem so vs % xem het", "",
            "| Dac diem | Nguong | Duoi nguong | Tren nguong | Chenh |",
            "|---|---|---|---|---|"]
    for k in ("duration", "parallax_share", "n_i2v", "hook_dur",
              "rest_dur", "n_shots", "n_sets", "n_motifs"):
        c = _split_compare(rows, k, M)
        if c:
            out.append(f"| `{k}` | {c['cut']} | {c['low']}% (n={c['low_n']}) | "
                       f"{c['high']}% (n={c['high_n']}) | **{c['delta']:+.1f}** |")

    out += ["", "## Dac diem phan loai", "",
            "> Cac nhom nay rat de bi nhieu dong bien: mua, gio trong ngay va",
            "> su co mat cua me thuong di kem nhau trong cung mot loat video.",
            "> Chenh lech o day la dau hieu de DI THU, khong phai ket luan.", ""]
    for k in ("hook_lane", "season", "time_of_day", "has_mother"):
        g = _group_compare(rows, k, M)
        if g:
            out.append(f"- `{k}`: " + " · ".join(
                f"{d['value']} **{d['avg']}%** (n={d['n']})" for d in g))

    out += ["", "## Viec can lam o lan brief sau", ""]
    hints = []
    for k, label in (("rest_dur", "nhip lang cuoi"),
                     ("parallax_share", "ti le parallax"),
                     ("hook_dur", "do dai hook"),
                     ("duration", "tong thoi luong")):
        c = _split_compare(rows, k, M)
        if c and abs(c["delta"]) >= 3.0:
            direc = "dai" if c["delta"] > 0 else "ngan"
            hints.append(f"- {label}: nhom {direc} hon dang hon "
                         f"**{abs(c['delta']):.1f} diem %**. Thu nghieng ve huong do.")
    hl = _group_compare(rows, "hook_lane", M)
    if len(hl) >= 2 and hl[0]["avg"] - hl[-1]["avg"] >= 3.0:
        hints.append(f"- hook bang `{hl[0]['value']}` dang hon `{hl[-1]['value']}` "
                     f"**{hl[0]['avg']-hl[-1]['avg']:.1f} diem %**.")
    out += hints or ["- Chua co khac biet nao du ro de hanh dong."]

    txt = "\n".join(out)
    (ROOT / "metrics-report.md").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"\n-> {ROOT/'metrics-report.md'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="YouTube Analytics -> brief")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest").set_defaults(func=cmd_ingest)
    f = sub.add_parser("fetch"); f.set_defaults(func=cmd_fetch)
    f.add_argument("--days", type=int, default=28)
    sub.add_parser("report").set_defaults(func=cmd_report)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
