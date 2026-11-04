"""
Khau publish — chay tren GitHub Actions, khong chay tren may nao cua ban.

    python -m publish.cli --next            # chon job san sang cu nhat
    python -m publish.cli --job jobs/x.yaml
    python -m publish.cli --next --dry-run
"""
from __future__ import annotations

import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import schema, state, qc  # noqa: E402
from publish import sharepack  # noqa: E402


def _enabled(name: str) -> bool:
    return os.environ.get(f"PUBLISH_{name.upper()}", "1") not in ("0", "false", "")


def find_next() -> Path | None:
    """Job cu nhat da qua QC va chua publish."""
    cands = []
    for yml in sorted((ROOT / "jobs").glob("*.yaml")):
        try:
            job = schema.load(yml)
        except Exception:
            continue
        ok, why = schema.publishable(job)
        if not ok:
            print(f"  bo qua {yml.name}: {why}")
            continue
        st = state.State(ROOT / "jobs" / job.id / "state.json")
        if st.stage("qc") == "done" and st.stage("publish") == "pending":
            cands.append((job.id, yml))
    return sorted(cands)[0][1] if cands else None


def run(job_path: Path, dry: bool = False) -> dict:
    job = schema.load(job_path)
    jdir = ROOT / "jobs" / job.id
    video = jdir / "out" / "final.mp4"
    st = state.State(jdir / "state.json")

    if not video.exists():
        raise FileNotFoundError(f"chua co video: {video}")

    ok, why = schema.publishable(job)
    if not ok:
        raise SystemExit(f"job nay khong duoc phep dang ({why}). "
                         "Dat publish.enabled: true khi that su muon dang.")

    # Cong chan cung: QC chay lai ngay truoc khi dang, khong tin state cu.
    res = qc.run(video, job)
    if not res["pass"]:
        fails = [c["name"] for c in res["checks"] if not c["pass"]]
        st.mark_stage("publish", "blocked_by_qc")
        raise SystemExit(f"QC FAIL, khong dang. Loi: {', '.join(fails)}")

    out: dict[str, object] = {"job": job.id, "dry_run": dry,
                              "at": datetime.now(timezone.utc).isoformat(),
                              "results": [], "errors": []}
    p = job.publish or {}

    targets = []
    if _enabled("youtube") and p.get("youtube"):
        targets.append(("youtube", lambda: __import__(
            "publish.youtube", fromlist=["upload"]).upload(
            video, p["youtube"]["title"], p["youtube"].get("description", ""),
            p["youtube"].get("tags", []))))
    if _enabled("facebook") and p.get("facebook"):
        targets.append(("facebook", lambda: __import__(
            "publish.facebook", fromlist=["upload"]).upload(
            video, p["facebook"].get("caption", ""))))
    if _enabled("x") and p.get("x"):
        targets.append(("x", lambda: __import__(
            "publish.x", fromlist=["upload"]).upload(video, p["x"]["text"])))

    for name, fn in targets:
        if dry:
            out["results"].append({"platform": name, "dry_run": True})
            continue
        try:
            r = fn()
            out["results"].append(r)
            print(f"  OK  {name}: {r.get('url')}")
        except Exception as e:                      # mot nen tang loi khong keo do ca lo
            out["errors"].append({"platform": name, "error": str(e)[:500]})
            print(f"  ERR {name}: {e}")

    yt = next((r for r in out["results"] if r.get("platform") == "youtube"), None)
    sp = sharepack.build(job, (yt or {}).get("url", "(chua co link)"),
                         jdir / "out" / "contact.jpg",
                         jdir / "out" / "share-pack.md")
    out["sharepack"] = sp

    (jdir / "out" / "publish.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    if not dry:
        st.mark_stage("publish", "done" if not out["errors"] else "partial")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--job", type=Path)
    g.add_argument("--next", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    jp = a.job or find_next()
    if jp is None:
        print("khong co job nao san sang de dang."); return 0
    print(f"publish: {jp}")
    res = run(jp, a.dry_run)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
