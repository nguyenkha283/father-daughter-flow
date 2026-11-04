#!/usr/bin/env python3
"""
Chuan bi dataset train LoRA. Chay tren may 1, truoc khi mo notebook Colab.

    python scripts/prep_dataset.py --kind girl --src raw/moonie --out training/girl

Lam 3 viec:
1. Cat/resize anh ve dung bucket do phan giai ma SDXL da duoc train
2. Sinh file caption .txt kem trigger token
3. Canh bao nhung thu lam hong LoRA: it anh qua, anh gan trung nhau, anh be
"""
from __future__ import annotations

import argparse, shutil, sys
from pathlib import Path

import cv2
import numpy as np

# SDXL duoc train tren cac bucket nay. Dua anh ve dung bucket cho ket qua
# on dinh hon nhieu so voi resize tuy y.
BUCKETS = [(1024, 1024), (896, 1152), (832, 1216), (768, 1344),
           (1152, 896), (1216, 832), (1344, 768)]

KINDS = {
    # kind:   (token,          so anh toi thieu, caption nen)
    "dad":    ("f4thr_man",    25, "a man"),
    "girl":   ("m00nie_girl",  35, "a toddler girl"),   # 2 tuoi kho giu nhat quan nhat
    "mother": ("m0ther_woman", 25, "a woman"),
    "style":  ("cozyhn_style", 30, "an interior scene"),
}
DUP_LIMIT = 0.93      # tren nguong nay coi nhu anh trung -> LoRA bi overfit
MIN_SIDE = 640


def ahash(img, n: int = 16) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (n, n), interpolation=cv2.INTER_AREA).astype(np.float32)
    return (g > g.mean()).flatten()


def best_bucket(w: int, h: int) -> tuple[int, int]:
    ar = w / h
    return min(BUCKETS, key=lambda b: abs((b[0] / b[1]) - ar))


def fit(img, bw: int, bh: int):
    """Scale phu kin bucket roi cat giua — khong bao gio bop meo ti le."""
    h, w = img.shape[:2]
    s = max(bw / w, bh / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA
                     if s < 1 else cv2.INTER_CUBIC)
    x, y = (nw - bw) // 2, (nh - bh) // 2
    return img[y:y + bh, x:x + bw]


def run(kind: str, src: Path, out: Path, caption: str | None,
        clean: bool = False) -> dict:
    token, min_n, default_cap = KINDS[kind]
    cap = caption or default_cap
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.iterdir()
                   if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    if not files:
        raise SystemExit(f"khong co anh nao trong {src}")

    kept, hashes, warn, skipped = [], [], [], []
    for f in files:
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            skipped.append((f.name, "khong doc duoc")); continue
        h, w = img.shape[:2]
        if min(w, h) < MIN_SIDE:
            skipped.append((f.name, f"qua be {w}x{h}, can canh ngan >= {MIN_SIDE}"))
            continue

        hh = ahash(img)
        dup = next((kept[i].name for i, o in enumerate(hashes)
                    if (hh == o).mean() > DUP_LIMIT), None)
        if dup:
            skipped.append((f.name, f"gan trung voi {dup}")); continue

        bw, bh = best_bucket(w, h)
        dst = out / f"{kind}_{len(kept):03d}.png"
        cv2.imwrite(str(dst), fit(img, bw, bh))
        dst.with_suffix(".txt").write_text(f"{token}, {cap}", encoding="utf-8")
        kept.append(dst); hashes.append(hh)

    if len(kept) < min_n:
        warn.append(f"chi co {len(kept)} anh, '{kind}' can >= {min_n}. "
                    "Thieu anh thi LoRA khong giu duoc nhan vat.")
    if len(kept) > 80:
        warn.append(f"{len(kept)} anh la nhieu; 40-60 anh chon ky tot hon.")

    sizes = {}
    for p in kept:
        im = cv2.imread(str(p)); sizes[f"{im.shape[1]}x{im.shape[0]}"] = \
            sizes.get(f"{im.shape[1]}x{im.shape[0]}", 0) + 1

    return {"kind": kind, "token": token, "caption": cap, "out": str(out),
            "kept": len(kept), "skipped": skipped, "warnings": warn,
            "buckets": sizes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Chuan bi dataset train LoRA")
    ap.add_argument("--kind", choices=list(KINDS), required=True)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--caption", help="caption nen, mac dinh theo kind")
    ap.add_argument("--clean", action="store_true", help="xoa thu muc out truoc")
    a = ap.parse_args(argv)

    r = run(a.kind, a.src, a.out, a.caption, a.clean)
    print(f"\n{r['kind']}  token='{r['token']}'  caption='{r['caption']}'")
    print(f"  giu lai : {r['kept']} anh -> {r['out']}")
    print(f"  bucket  : {r['buckets']}")
    if r["skipped"]:
        print(f"  bo qua  : {len(r['skipped'])}")
        for n, why in r["skipped"][:10]:
            print(f"      {n}: {why}")
    for w in r["warnings"]:
        print(f"  CANH BAO: {w}")
    print("\n=> " + ("san sang train" if not r["warnings"]
                     else "xu ly canh bao truoc khi train"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
