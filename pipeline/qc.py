"""
QC tu dong — chan video hong TRUOC khi publish.

Fail o day thi job chuyen sang 'needs_review', khong bao gio tu dang.
"""
from __future__ import annotations

import argparse, json, re, subprocess, sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import schema  # noqa: E402

AR_TOL = 0.01
LUFS_TOL = 1.5
HOOK_MIN_LUMA = 28.0      # frame dau khong duoc gan nhu den
SAFE_TOP, SAFE_BOT = 0.10, 0.18   # UI cua Shorts an mep tren/duoi


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams",
                        "-show_format", "-of", "json", str(p)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def _loudness(p: Path) -> float | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p),
                        "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s*(-?\d+\.?\d*)\s*LUFS", r.stderr)
    return float(m[-1]) if m else None


def _frames(p: Path, k: int = 12):
    cap = cv2.VideoCapture(str(p))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    out = []
    for i in range(k):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * (n - 1) / max(1, k - 1)))
        ok, fr = cap.read()
        if ok:
            out.append(fr)
    cap.release()
    return out


def contact_sheet(p: Path, out: Path, cols: int = 4, k: int = 12) -> Path:
    fr = _frames(p, k)
    if not fr:
        raise RuntimeError("khong doc duoc frame nao")
    h, w = fr[0].shape[:2]
    tw = 300; th = int(h * tw / w)
    thumbs = [cv2.resize(f, (tw, th)) for f in fr]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    return out


def run(video: Path, job: schema.Job | None = None,
        sheet: Path | None = None) -> dict:
    info = _probe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    w, h = int(v["width"]), int(v["height"])
    dur = float(info["format"]["duration"])
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den)

    lufs = _loudness(video) if a else None
    frames = _frames(video, 12)
    first_luma = float(cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY).mean()) if frames else 0.0
    # phat hien frame dung hinh hoan toan (dau hieu render hong)
    diffs = [float(np.abs(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32)
                          - cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY).astype(np.float32)).mean())
             for i in range(1, len(frames))]
    target = job.target_lufs if job else -14.0

    checks = [
        ("ti le khung 9:16", abs((w / h) - (9 / 16)) < AR_TOL, f"{w}x{h}"),
        ("do phan giai >= 832x1472", w >= 832 and h >= 1472, f"{w}x{h}"),
        ("thoi luong 30-60s", 30.0 <= dur <= 60.0, f"{dur:.2f}s"),
        ("fps ~30", abs(fps - 30.0) < 0.6, f"{fps:.2f}"),
        ("co track audio", a is not None, a["codec_name"] if a else "KHONG"),
        ("loudness dat muc tieu",
         lufs is not None and abs(lufs - target) <= LUFS_TOL,
         f"{lufs:.2f} LUFS (muc tieu {target})" if lufs else "khong do duoc"),
        ("frame dau khong den (hook song)",
         first_luma >= HOOK_MIN_LUMA, f"luma {first_luma:.1f}"),
        ("khong co doan dung hinh",
         all(d > 0.15 for d in diffs) if diffs else False,
         f"min diff {min(diffs):.3f}" if diffs else "n/a"),
    ]
    if job:
        checks.append(("khop thoi luong job",
                       abs(dur - job.duration) < 2.5,
                       f"job {job.duration}s vs render {dur:.2f}s"))

    sheet_path = str(contact_sheet(video, sheet)) if sheet else None
    passed = all(c[1] for c in checks)
    return {"video": str(video), "pass": passed, "contact_sheet": sheet_path,
            "checks": [{"name": n, "pass": bool(p), "value": val}
                       for n, p, val in checks]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="QC tu dong")
    p.add_argument("video", type=Path)
    p.add_argument("--job", type=Path, default=None)
    p.add_argument("--sheet", type=Path, default=None)
    a = p.parse_args(argv)
    job = schema.load(a.job) if a.job else None
    res = run(a.video, job, a.sheet)
    for c in res["checks"]:
        print(("  PASS  " if c["pass"] else "  FAIL  ") + f"{c['name']:34s} {c['value']}")
    print("\n=> " + ("QC PASS" if res["pass"] else "QC FAIL -> needs_review"))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
