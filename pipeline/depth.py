"""
Sinh depth map cho keyframe. Chay local (CPU cung duoc) — model chi 25M tham so.

Depth-Anything-V2-Small xuat anh xam: cang SANG = cang GAN, dung dung chuan
ma parallax.load_disparity() mong doi.
"""
from __future__ import annotations

import argparse, sys
from pathlib import Path

import cv2
import numpy as np

_PIPE = None


def _pipe():
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline as hf  # import tre, khong bat buoc cai
        import torch
        dev = 0 if torch.cuda.is_available() else -1
        _PIPE = hf(task="depth-estimation",
                   model="depth-anything/Depth-Anything-V2-Small-hf",
                   device=dev)
    return _PIPE


def estimate(still: Path, out: Path) -> Path:
    from PIL import Image
    d = _pipe()(Image.open(still).convert("RGB"))["depth"]
    arr = np.array(d).astype(np.float32)
    lo, hi = arr.min(), arr.max()
    arr = (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), (arr * 255).astype(np.uint8))
    return out


def estimate_fallback(still: Path, out: Path) -> Path:
    """
    Depth gia lap khi chua cai torch — CHI dung de thu pipeline, khong dung that.

    Gia dinh tho: day khung hinh = gan, dinh khung = xa; co dieu chinh theo
    do sac net cuc bo (vung net thuong la tien canh).
    """
    img = cv2.imread(str(still), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(still)
    h, w = img.shape
    grad = np.linspace(0.15, 1.0, h, dtype=np.float32)[:, None].repeat(w, 1)
    sharp = cv2.Laplacian(img.astype(np.float32), cv2.CV_32F, ksize=3)
    sharp = cv2.GaussianBlur(np.abs(sharp), (31, 31), 0)
    sharp = sharp / (sharp.max() + 1e-6)
    d = np.clip(0.75 * grad + 0.25 * sharp, 0, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), (d * 255).astype(np.uint8))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Sinh depth map")
    p.add_argument("stills", type=Path, nargs="+")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--fallback", action="store_true",
                   help="dung depth gia lap, chi de thu pipeline")
    a = p.parse_args(argv)
    fn = estimate_fallback if a.fallback else estimate
    for s in a.stills:
        print(fn(s, a.outdir / f"{s.stem}.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
