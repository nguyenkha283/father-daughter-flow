#!/usr/bin/env python3
"""
CLI dieu phoi — day la thu Claude Code goi.

    python run.py status   jobs/example.yaml
    python run.py depth    jobs/example.yaml [--fallback]
    python run.py animate  jobs/example.yaml        # lane parallax, local
    python run.py export   jobs/example.yaml ...    # dong goi viec cho Colab
    python run.py import   jobs/example.yaml        # thu ket qua tu Colab ve
    python run.py assemble jobs/example.yaml
    python run.py qc       jobs/example.yaml
    python run.py all      jobs/example.yaml        # chay het phan chay duoc
"""
from __future__ import annotations

import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline import schema, state, assemble, qc  # noqa: E402
from pipeline.parallax import render  # noqa: E402

COLAB = ROOT / "colab_bridge"      # thu muc nay dong bo voi Drive qua rclone


def _load(p: Path):
    job = schema.load(p)
    errs = schema.validate(job)
    if errs:
        print("JOB KHONG HOP LE:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    for w in schema.warnings(job):
        print("  warn:", w)
    jdir = ROOT / "jobs" / job.id
    st = state.State(jdir / "state.json")
    cleared = st.reconcile([s.id for s in job.shots], jdir)
    if cleared:
        print(f"  reconcile: {len(cleared)} artifact mat file, da xoa co: "
              f"{', '.join(cleared[:6])}{' ...' if len(cleared) > 6 else ''}")
    return job, jdir, st


# --------------------------------------------------------------------------- #
def cmd_status(a):
    job, jdir, st = _load(a.job)
    ids = [s.id for s in job.shots]
    print(f"{job.id}\n  {len(job.shots)} shot · {job.duration}s · "
          f"parallax {job.parallax_share:.0%} · i2v {len(job.i2v_shots)}")
    print("  artifacts:", json.dumps(st.progress(ids)))
    print("  stages   :", json.dumps({s: st.stage(s) for s in state.STAGES}))
    miss = {a_: st.todo(ids, a_) for a_ in state.ARTIFACTS}
    for k, v in miss.items():
        if v:
            print(f"  thieu {k}: {', '.join(v)}")


def cmd_depth(a):
    from pipeline import depth
    job, jdir, st = _load(a.job)
    fn = depth.estimate_fallback if a.fallback else depth.estimate
    for s in job.shots:
        if st.has(s.id, "depth"):
            continue
        still = jdir / "stills" / f"{s.id}.png"
        if not still.exists():
            print(f"  bo qua {s.id}: chua co still"); continue
        fn(still, jdir / "depth" / f"{s.id}.png")
        st.mark(s.id, "depth"); print(f"  depth {s.id}")
    st.mark_stage("depth")


def cmd_animate(a):
    """Chi lane parallax. Shot i2v do Colab lo."""
    job, jdir, st = _load(a.job)
    done = pending = 0
    for s in job.shots:
        if st.has(s.id, "clip"):
            continue
        if s.lane == "i2v":
            pending += 1; continue
        still, dep = jdir / "stills" / f"{s.id}.png", jdir / "depth" / f"{s.id}.png"
        if not (still.exists() and dep.exists()):
            print(f"  bo qua {s.id}: thieu still/depth"); continue
        render(still, dep, jdir / "clips" / f"{s.id}.mp4",
               s.move, s.duration, encoder=a.encoder)
        st.mark(s.id, "clip"); done += 1
        print(f"  parallax {s.id} ({s.move}, {s.duration}s)")
    print(f"-> {done} clip parallax xong, {pending} shot i2v cho Colab")
    st.mark_stage("animate", "done" if pending == 0 else "partial")


def cmd_export(a):
    """Gom viec GPU cua nhieu job thanh 1 batch cho 1 phien Colab."""
    inbox = COLAB / "inbox"; inbox.mkdir(parents=True, exist_ok=True)
    batch, n_still, n_i2v = [], 0, 0
    for jp in a.job:
        job, jdir, st = _load(jp)
        ids = [s.id for s in job.shots]
        items = []
        for s in job.shots:
            need_still = not st.has(s.id, "still")
            need_clip = s.lane == "i2v" and not st.has(s.id, "clip")
            if not (need_still or need_clip):
                continue
            items.append({"shot": s.id, "prompt": s.prompt,
                          "negative": s.negative, "seed": s.seed,
                          "need_still": need_still, "need_i2v": need_clip,
                          "duration": s.duration})
            n_still += need_still; n_i2v += need_clip
            if need_clip and not need_still:
                src = jdir / "stills" / f"{s.id}.png"
                if src.exists():
                    dst = inbox / job.id / "stills"; dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst / f"{s.id}.png")
        if items:
            batch.append({"job": job.id, "season": job.season,
                          "time": job.time, "items": items})
    (inbox / "batch.json").write_text(
        json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")
    est = n_still * 35 + n_i2v * 90
    print(f"-> {inbox/'batch.json'}")
    print(f"   {len(batch)} job · {n_still} keyframe · {n_i2v} clip i2v")
    print(f"   uoc tinh GPU T4: ~{est//60} phut "
          f"({'VUA 1 phien' if est < 3.5*3600 else 'CAN CHIA 2 phien'})")


def cmd_import(a):
    """Thu ket qua Colab tu outbox ve job, danh dau state."""
    job, jdir, st = _load(a.job)
    out = COLAB / "outbox" / job.id
    if not out.exists():
        print(f"chua co {out}"); return
    got = 0
    for kind, sub, art in (("stills", "stills", "still"), ("clips", "clips", "clip")):
        src = out / sub
        if not src.exists():
            continue
        for f in sorted(src.glob("*")):
            sid = f.stem
            dst = jdir / sub / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst); st.mark(sid, art); got += 1
    print(f"-> thu ve {got} file")
    cmd_status(a)


def cmd_assemble(a):
    job, jdir, st = _load(a.job)
    missing = [s.id for s in job.shots if not (jdir / "clips" / f"{s.id}.mp4").exists()]
    if missing:
        print("chua ghep duoc, thieu clip:", ", ".join(missing)); sys.exit(1)
    print(json.dumps(assemble.build(job, ROOT, jdir / "out" / "final.mp4",
                                    encoder=a.encoder), ensure_ascii=False))
    st.mark_stage("assemble")


def cmd_qc(a):
    job, jdir, st = _load(a.job)
    res = qc.run(jdir / "out" / "final.mp4", job, jdir / "out" / "contact.jpg")
    for c in res["checks"]:
        print(("  PASS  " if c["pass"] else "  FAIL  ") + f"{c['name']:32s} {c['value']}")
    st.mark_stage("qc", "done" if res["pass"] else "needs_review")
    (jdir / "out" / "qc.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print("=> " + ("QC PASS — san sang publish" if res["pass"]
                   else "QC FAIL -> needs_review"))
    sys.exit(0 if res["pass"] else 1)


def cmd_all(a):
    cmd_depth(a); cmd_animate(a)
    job, jdir, st = _load(a.job)
    if st.stage("animate") != "done":
        print("\nCon shot i2v chua co clip. Chay:  python run.py export <job>")
        print("roi chay notebook Colab, roi:      python run.py import <job>")
        return
    cmd_assemble(a); cmd_qc(a)


def main(argv=None):
    p = argparse.ArgumentParser(prog="run.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, multi in [("status", cmd_status, False), ("depth", cmd_depth, False),
                            ("animate", cmd_animate, False), ("export", cmd_export, True),
                            ("import", cmd_import, False), ("assemble", cmd_assemble, False),
                            ("qc", cmd_qc, False), ("all", cmd_all, False)]:
        sp = sub.add_parser(name)
        sp.add_argument("job", type=Path, nargs="+" if multi else None)
        sp.add_argument("--encoder", default="libx264")
        sp.add_argument("--fallback", action="store_true")
        sp.set_defaults(func=fn)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
