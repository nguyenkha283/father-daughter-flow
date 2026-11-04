"""Dung canh gia lap roi do xem parallax co THAT su xay ra khong."""
import subprocess, sys, json
from pathlib import Path
import numpy as np, cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.parallax import render  # noqa: E402

W, H = 832, 1472
TMP = ROOT / "tests" / "_tmp"
TMP.mkdir(parents=True, exist_ok=True)


def make_scene():
    """Canh ban cong: troi + toa nha xa (xa), khung cua (giua), chau cay (gan)."""
    img = np.zeros((H, W, 3), np.uint8)
    dep = np.zeros((H, W), np.uint8)

    # --- XA: troi chuyen sac + cac toa nha ---
    for y in range(H):
        f = y / H
        img[y, :] = (int(200 - 60 * f), int(175 - 30 * f), int(150 + 20 * f))
    dep[:, :] = 20
    rng = np.random.default_rng(7)
    for bx in range(0, W, 95):
        bh = int(rng.integers(260, 620)); bw = int(rng.integers(55, 88))
        cv2.rectangle(img, (bx, H - 780 - bh), (bx + bw, H - 780), (150, 142, 132), -1)
        cv2.rectangle(dep, (bx, H - 780 - bh), (bx + bw, H - 780), 42, -1)

    # --- GIUA: khung cua nhom kinh ---
    cv2.rectangle(img, (60, 300), (W - 60, H - 300), (122, 154, 139), 26)
    cv2.rectangle(dep, (60, 300), (W - 60, H - 300), 132, 26)
    cv2.line(img, (W // 2, 300), (W // 2, H - 300), (122, 154, 139), 18)
    cv2.line(dep, (W // 2, 300), (W // 2, H - 300), 132, 18)

    # --- GAN: chau hung que goc duoi + ghe nhua do ---
    cv2.ellipse(img, (175, H - 210), (155, 115), 0, 0, 360, (70, 120, 80), -1)
    cv2.ellipse(dep, (175, H - 210), (155, 115), 0, 0, 360, 240, -1)
    cv2.rectangle(img, (95, H - 185), (255, H - 55), (62, 92, 138), -1)
    cv2.rectangle(dep, (95, H - 185), (255, H - 55), 240, -1)
    cv2.rectangle(img, (W - 300, H - 260), (W - 90, H - 60), (62, 81, 201), -1)
    cv2.rectangle(dep, (W - 300, H - 260), (W - 90, H - 60), 250, -1)

    cv2.imwrite(str(TMP / "still.png"), img)
    cv2.imwrite(str(TMP / "depth.png"), dep)


def frames(path, idxs):
    cap = cv2.VideoCapture(str(path))
    got, i = {}, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i in idxs:
            got[i] = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        i += 1
    cap.release()
    return got, i


def shift_in(a, b, y0, y1, x0, x1):
    """Do dich chuyen ngang giua 2 frame trong 1 vung, bang phase correlation."""
    wa = cv2.createHanningWindow((x1 - x0, y1 - y0), cv2.CV_32F)
    (dx, _), _ = cv2.phaseCorrelate(a[y0:y1, x0:x1].copy(),
                                    b[y0:y1, x0:x1].copy(), wa)
    return dx


def main():
    make_scene()
    info = render(TMP / "still.png", TMP / "depth.png", TMP / "out.mp4",
                  move="drift_right", duration=3.0)
    print("render:", json.dumps(info))

    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,nb_frames,r_frame_rate", "-of", "json",
         str(TMP / "out.mp4")], capture_output=True, text=True)
    st = json.loads(pr.stdout)["streams"][0]
    print("ffprobe:", st)

    fr, total = frames(TMP / "out.mp4", {0, 89})
    a, b = fr[0], fr[89]

    # Vung GAN = goc duoi (chau cay, ghe). Vung XA = troi + toa nha o tren.
    near = abs(shift_in(a, b, H - 330, H - 40, 40, W - 40))
    far = abs(shift_in(a, b, 120, 560, 40, W - 40))

    print(f"\ntong frame decode duoc : {total}")
    print(f"dich chuyen vung GAN   : {near:6.2f} px")
    print(f"dich chuyen vung XA    : {far:6.2f} px")
    print(f"ti le gan/xa           : {near / max(far, 1e-6):6.2f}x")

    ok = True
    checks = [
        ("do phan giai 832x1472", (st["width"], st["height"]) == (W, H)),
        ("du 90 frame @30fps", total == 90),
        ("vung gan co dich chuyen", near > 1.0),
        ("gan dich nhieu hon xa (parallax that)", near > far * 1.8),
        ("bien do du nho de giu cam giac tinh", near < W * MAXP),
    ]
    for name, good in checks:
        print(("  PASS  " if good else "  FAIL  ") + name)
        ok &= good
    print("\n=> " + ("TAT CA PASS" if ok else "CO CHECK FAIL"))
    return 0 if ok else 1


MAXP = 0.05
if __name__ == "__main__":
    sys.exit(main())
