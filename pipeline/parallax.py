"""
2.5D parallax renderer — "lane A" của pipeline Father and Daughter.

Biến 1 keyframe tĩnh + 1 depth map thành clip có chuyển động camera mềm,
chạy hoàn toàn trên CPU/GPU yếu. Đây là lane MIỄN PHÍ, gánh ~70% số shot,
nên mọi shot không thực sự cần chuyển động vật thể đều nên đi qua đây.

Dùng:
    python -m pipeline.parallax --still stills/shot_01.png \
        --depth depth/shot_01.png --out clips/shot_01.mp4 \
        --move drift_right --duration 4.0
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

FPS = 30
# Biên độ dịch tối đa tính theo % chiều rộng. Giữ NHỎ — chủ đề "bình yên"
# cần chuyển động gần như không nhận ra. Trên 3% là bắt đầu lộ artifact
# ở rìa vật thể và mất cảm giác tĩnh tại.
MAX_SHIFT_PCT = 0.022
# Vùng đệm quanh khung để không bao giờ lòi mép đen khi warp.
OVERSIZE = 1.12


# --------------------------------------------------------------------------- #
# Đường chuyển động camera
# --------------------------------------------------------------------------- #
def smoothstep(t: float) -> float:
    """Ease in-out. Chuyển động tuyến tính trông như máy móc, cái này thì không."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Camera:
    tx: float  # dịch ngang, đơn vị = tỉ lệ chiều rộng
    ty: float  # dịch dọc
    zoom: float  # >0 là đẩy vào, <0 là lùi ra


def camera_at(move: str, t: float, amount: float = 1.0) -> Camera:
    """t trong [0,1] là tiến độ của shot."""
    e = smoothstep(t)
    a = amount

    # Hơi thở nền: luôn bật. Đây là thứ khiến khung hình tĩnh vẫn "sống"
    # mà người xem không chỉ ra được tại sao.
    breathe = 0.004 * a * np.sin(2.0 * np.pi * t * 0.75)

    if move == "static":
        return Camera(0.0, 0.0, breathe)
    if move == "drift_right":
        return Camera((e - 0.5) * 2.0 * a, 0.0, breathe)
    if move == "drift_left":
        return Camera(-(e - 0.5) * 2.0 * a, 0.0, breathe)
    if move == "drift_up":
        return Camera(0.0, -(e - 0.5) * 2.0 * a, breathe)
    if move == "drift_down":
        return Camera(0.0, (e - 0.5) * 2.0 * a, breathe)
    if move == "push_in":
        return Camera(0.0, 0.0, e * 0.06 * a + breathe)
    if move == "pull_out":
        return Camera(0.0, 0.0, (1.0 - e) * 0.06 * a + breathe)
    if move == "float":
        # Số 8 rất chậm. Dùng cho shot dài, cảnh ngủ, cảnh nhìn ra cửa sổ.
        return Camera(
            a * 0.7 * float(np.sin(2.0 * np.pi * t)),
            a * 0.35 * float(np.sin(4.0 * np.pi * t)),
            breathe,
        )
    raise ValueError(f"move khong ho tro: {move}")


MOVES = [
    "static", "drift_right", "drift_left", "drift_up",
    "drift_down", "push_in", "pull_out", "float",
]


# --------------------------------------------------------------------------- #
# Warp theo chiều sâu
# --------------------------------------------------------------------------- #
def load_disparity(path: Path, size: tuple[int, int]) -> np.ndarray:
    """
    Trả về disparity chuẩn hoá 0..1, trong đó 1 = GẦN máy quay.

    Depth-Anything xuất ra ảnh xám càng sáng càng gần, nên dùng trực tiếp.
    Làm mượt mạnh là chủ ý: biên depth sắc sẽ xé rách ảnh khi warp, mà
    chuyển động của ta quá nhỏ nên không cần biên chính xác.
    """
    d = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if d is None:
        raise FileNotFoundError(f"khong doc duoc depth: {path}")
    d = cv2.resize(d, size, interpolation=cv2.INTER_LINEAR).astype(np.float32)
    lo, hi = float(d.min()), float(d.max())
    d = (d - lo) / (hi - lo) if hi > lo else np.zeros_like(d)
    k = max(3, int(size[0] * 0.02) | 1)
    return cv2.GaussianBlur(d, (k, k), 0)


def warp(img: np.ndarray, disp: np.ndarray, cam: Camera,
         out_w: int, out_h: int) -> np.ndarray:
    """Dựng 1 frame: lấy mẫu ngược từ ảnh phóng to, cắt về đúng khung."""
    H, W = img.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    ix0, iy0 = (W - out_w) // 2, (H - out_h) // 2

    xs = np.arange(out_w, dtype=np.float32) + ix0
    ys = np.arange(out_h, dtype=np.float32) + iy0
    bx, by = np.meshgrid(xs, ys)

    # disp dang o kich thuoc phong to; lay dung cua so se xuat ra.
    d = disp[iy0:iy0 + out_h, ix0:ix0 + out_w]

    # Vật ở gần dịch nhiều hơn vật ở xa — đây chính là hiệu ứng parallax.
    shift = MAX_SHIFT_PCT * W
    bx = bx - cam.tx * shift * d
    by = by - cam.ty * shift * d

    # Dolly: vật gần phóng to nhanh hơn nền.
    if abs(cam.zoom) > 1e-6:
        s = 1.0 + cam.zoom * (0.35 + 0.65 * d)
        bx = cx + (bx - cx) / s
        by = cy + (by - cy) / s

    # cv2.remap doi dung CV_32FC1, nen ep kieu truoc khi goi.
    bx = np.ascontiguousarray(bx, dtype=np.float32)
    by = np.ascontiguousarray(by, dtype=np.float32)
    return cv2.remap(img, bx, by, cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_REFLECT_101)


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(still: Path, depth: Path, out: Path, move: str,
           duration: float, amount: float = 1.0,
           encoder: str = "libx264", fps: int = FPS) -> dict:
    img0 = cv2.imread(str(still), cv2.IMREAD_COLOR)
    if img0 is None:
        raise FileNotFoundError(f"khong doc duoc still: {still}")
    out_h, out_w = img0.shape[:2]

    big = (int(round(out_w * OVERSIZE)) // 2 * 2,
           int(round(out_h * OVERSIZE)) // 2 * 2)
    img = cv2.resize(img0, big, interpolation=cv2.INTER_CUBIC)
    disp = load_disparity(depth, big)

    n_frames = max(1, int(round(duration * fps)))
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", encoder, "-pix_fmt", "yuv420p",
    ]
    cmd += (["-cq", "19", "-preset", "p5"] if "nvenc" in encoder
            else ["-crf", "17", "-preset", "slow"])
    cmd.append(str(out))

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for i in range(n_frames):
        t = i / max(1, n_frames - 1)
        frame = warp(img, disp, camera_at(move, t, amount), out_w, out_h)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg loi khi encode")

    return {"out": str(out), "frames": n_frames,
            "size": [out_w, out_h], "move": move, "duration": duration}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="2.5D parallax renderer")
    p.add_argument("--still", type=Path, required=True)
    p.add_argument("--depth", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--move", choices=MOVES, default="static")
    p.add_argument("--duration", type=float, default=4.0)
    p.add_argument("--amount", type=float, default=1.0,
                   help="he so bien do, 0.5 = nua, 2.0 = gap doi")
    p.add_argument("--encoder", default="libx264",
                   help="dung h264_nvenc tren may co GPU NVIDIA")
    p.add_argument("--fps", type=int, default=FPS)
    a = p.parse_args(argv)
    info = render(a.still, a.depth, a.out, a.move, a.duration,
                  a.amount, a.encoder, a.fps)
    print(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
