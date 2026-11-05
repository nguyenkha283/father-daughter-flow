"""
Cau noi rclone giua may ban, Google Drive, Colab va GitHub Actions.

Bon noi khong thay file cua nhau. Drive la kho trung gian duy nhat, va cau
truc thu muc tren Drive PHAI khop voi cai ma Colab worker va workflow Actions
mong doi — sai mot cap thu muc la ca pipeline dung im ma khong bao loi gi.

    father-and-daughter/
      inbox/     <- may 1 day len   -> Colab doc
      outbox/    <- Colab ghi ra    -> may 1 keo ve
      training/  <- may 1 day len   -> notebook train LoRA doc
      loras/     <- notebook ghi ra -> Colab worker doc
      final/     <- may 1 day len   -> GitHub Actions keo ve de dang
                    final/<job-id>/out/final.mp4
"""
from __future__ import annotations

import argparse, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import schema, state  # noqa: E402

REMOTE = os.environ.get("RCLONE_REMOTE", "gdrive")
BASE = os.environ.get("RCLONE_BASE", "father-and-daughter")


def remote(sub: str) -> str:
    return f"{REMOTE}:{BASE}/{sub}"


def _run(cmd: list[str], dry: bool) -> int:
    print("  $ " + " ".join(cmd))
    if dry:
        return 0
    if shutil.which("rclone") is None:
        print("  !! chua cai rclone. Xem https://rclone.org/install/")
        return 1
    return subprocess.run(cmd).returncode


def push_batch(dry: bool) -> int:
    """May 1 -> Drive: giao viec GPU cho Colab."""
    src = ROOT / "colab_bridge" / "inbox"
    if not (src / "batch.json").exists():
        print("chua co batch.json. Chay 'python run.py export <job>...' truoc.")
        return 1
    return _run(["rclone", "sync", str(src), remote("inbox"),
                 "--progress", "--checksum"], dry)


def pull_colab(dry: bool) -> int:
    """Drive -> may 1: thu ket qua Colab ve."""
    dst = ROOT / "colab_bridge" / "outbox"
    dst.mkdir(parents=True, exist_ok=True)
    return _run(["rclone", "sync", remote("outbox"), str(dst),
                 "--progress", "--checksum"], dry)


def push_training(dry: bool) -> int:
    """May 1 -> Drive: dataset cho notebook train LoRA."""
    src = ROOT / "training"
    if not src.exists():
        print("chua co thu muc training/. Chay scripts/prep_dataset.py truoc.")
        return 1
    return _run(["rclone", "sync", str(src), remote("training"),
                 "--progress", "--checksum"], dry)


def pull_loras(dry: bool) -> int:
    """Drive -> may 1: LoRA da train, de xem preview."""
    dst = ROOT / "loras"
    dst.mkdir(parents=True, exist_ok=True)
    return _run(["rclone", "copy", remote("loras"), str(dst), "--progress"], dry)


def push_final(dry: bool, job_path: Path | None = None) -> int:
    """
    May 1 -> Drive: video da qua QC, de GitHub Actions keo ve ma dang.

    Chi day job da qua QC. Day video chua QC len la mo duong cho cron dang
    nham mot ban hong.
    """
    jobs = [job_path] if job_path else sorted((ROOT / "jobs").glob("*.yaml"))
    pushed, skipped = 0, []
    for yml in jobs:
        try:
            job = schema.load(yml)
        except Exception as e:
            skipped.append((yml.name, f"doc loi: {e}")); continue
        jdir = ROOT / "jobs" / job.id
        st = state.State(jdir / "state.json")
        video = jdir / "out" / "final.mp4"

        if not video.exists():
            skipped.append((yml.name, "chua co final.mp4")); continue
        if st.stage("qc") != "done":
            skipped.append((yml.name, f"qc={st.stage('qc')}, chua dat")); continue
        ok, why = schema.publishable(job)
        if not ok:
            skipped.append((yml.name, why)); continue

        # Cau truc phai khop voi --include "*/out/final.mp4" trong workflow.
        rc = _run(["rclone", "copy", str(jdir / "out"),
                   f"{remote('final')}/{job.id}/out",
                   "--include", "final.mp4", "--include", "contact.jpg",
                   "--progress"], dry)
        if rc == 0:
            pushed += 1
        else:
            skipped.append((yml.name, "rclone loi"))

    print(f"\n-> day len {pushed} job")
    for n, why in skipped:
        print(f"   bo qua {n}: {why}")
    if pushed:
        print("\nNho commit state.json roi push len GitHub — Actions doc trang thai\n"
              "qc/publish tu git, khong phai tu Drive:")
        print("   git add jobs/*/state.json && git commit -m 'qc xong' && git push")
    return 0


def check(dry: bool) -> int:
    """Kiem tra rclone va remote co san sang khong."""
    if shutil.which("rclone") is None:
        print("  THIEU  rclone chua duoc cai — https://rclone.org/install/")
        return 1
    print("  OK     rclone:", subprocess.run(
        ["rclone", "version"], capture_output=True, text=True
    ).stdout.splitlines()[0])
    r = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True)
    remotes = [x.strip().rstrip(":") for x in r.stdout.split()]
    if REMOTE in remotes:
        print(f"  OK     remote '{REMOTE}' da cau hinh")
    else:
        print(f"  THIEU  remote '{REMOTE}' chua co. Chay: rclone config")
        print(f"         (da cau hinh: {remotes or 'khong co'})")
        return 1
    for sub in ("inbox", "outbox", "training", "loras", "final"):
        subprocess.run(["rclone", "mkdir", remote(sub)], capture_output=True)
    print(f"  OK     da tao du 5 thu muc tren {REMOTE}:{BASE}/")
    return 0


ACTIONS = {"check": check, "push-batch": push_batch, "pull-colab": pull_colab,
           "push-training": push_training, "pull-loras": pull_loras,
           "push-final": push_final}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=list(ACTIONS))
    ap.add_argument("--job", type=Path, default=None, help="chi voi push-final")
    ap.add_argument("--dry-run", action="store_true", help="chi in lenh, khong chay")
    a = ap.parse_args(argv)
    fn = ACTIONS[a.action]
    print(f"[{a.action}] remote={REMOTE}:{BASE}" + ("  (dry-run)" if a.dry_run else ""))
    return fn(a.dry_run, a.job) if fn is push_final else fn(a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
