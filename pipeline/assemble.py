"""
Ghep clip -> video cuoi: xfade, nhac nen, ambient, grade am, grain, loudnorm.

Chay tren CPU/NVENC o may 1 hoac may 2. Khong can GPU manh.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import schema  # noqa: E402

XFADE = schema.XFADE   # chuyen canh mem; chu de "binh yen" khong dung cut cung
FADE_OUT = 0.6       # chi fade o CUOI
AFADE_IN = 0.35      # audio duoc phep fade vao, video thi KHONG
MUSIC_VOL = 0.85
AMBIENT_VOL = 0.40


def _probe_dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def build(job: schema.Job, root: Path, out: Path,
          encoder: str = "libx264", grain: bool = True,
          xfade: float = XFADE) -> dict:
    jdir = root / "jobs" / job.id
    clips = []
    for s in job.shots:
        c = jdir / "clips" / f"{s.id}.mp4"
        if not c.exists():
            raise FileNotFoundError(f"thieu clip {c}")
        clips.append(c)

    durs = [_probe_dur(c) for c in clips]
    n = len(clips)
    total = sum(durs) - (n - 1) * xfade

    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]

    # --- audio inputs ---
    music = root / job.music if job.music else None
    has_music = bool(music and music.exists())
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
    amb_paths = [root / a for a in job.ambient if (root / a).exists()]
    for a in amb_paths:
        inputs += ["-stream_loop", "-1", "-i", str(a)]

    # --- chuoi xfade ---
    fc: list[str] = []
    cur, off = "[0:v]", 0.0
    for i in range(1, n):
        off += durs[i - 1] - xfade
        lbl = f"[vx{i}]"
        fc.append(f"{cur}[{i}:v]xfade=transition=fade:"
                  f"duration={xfade}:offset={off:.3f}{lbl}")
        cur = lbl

    # --- grade am + grain + fade ---
    # Khong co fade-in tu den: 1.5 giay dau la toan bo so phan cua video,
    # mo dau bang man den la vut di nua giay dat nhat (QC se bat loi nay).
    vchain = [f"fade=t=out:st={max(0.0, total - FADE_OUT):.3f}:d={FADE_OUT}"]
    # Hoi am mau va nang nhe gamma vung toi -> cam giac "am ap trong nha"
    vchain.insert(0, "eq=saturation=1.04:gamma_r=1.03:gamma_b=0.985")
    if grain:
        vchain.append("noise=alls=5:allf=t+u")   # grain giay, chong banding
    vchain.append("format=yuv420p")
    fc.append(f"{cur}{','.join(vchain)}[vout]")

    # --- audio ---
    a_idx = n
    a_lbls = []
    if has_music:
        fc.append(f"[{a_idx}:a]volume={MUSIC_VOL}[am]")
        a_lbls.append("[am]"); a_idx += 1
    for k in range(len(amb_paths)):
        fc.append(f"[{a_idx}:a]volume={AMBIENT_VOL}[aa{k}]")
        a_lbls.append(f"[aa{k}]"); a_idx += 1

    if a_lbls:
        mix = ("".join(a_lbls) +
               f"amix=inputs={len(a_lbls)}:duration=longest:normalize=0[amx]"
               ) if len(a_lbls) > 1 else f"{a_lbls[0]}anull[amx]"
        fc.append(mix)
        fc.append(f"[amx]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d={AFADE_IN},"
                  f"afade=t=out:st={max(0.0, total - FADE_OUT):.3f}:d={FADE_OUT},"
                  f"loudnorm=I={job.target_lufs}:TP=-1.5:LRA=11[aout]")

    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(fc), "-map", "[vout]"]
    if a_lbls:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", encoder]
    cmd += (["-cq", "20", "-preset", "p5"] if "nvenc" in encoder
            else ["-crf", "18", "-preset", "medium"])
    cmd += ["-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg loi:\n" + r.stderr[-2500:])

    return {"out": str(out), "clips": n, "duration": round(total, 2),
            "music": has_music, "ambient": len(amb_paths), "encoder": encoder}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Ghep video cuoi")
    p.add_argument("job", type=Path)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--encoder", default="libx264")
    p.add_argument("--no-grain", action="store_true")
    a = p.parse_args(argv)

    job = schema.load(a.job)
    errs = schema.validate(job)
    if errs:
        print("job khong hop le:"); [print("  -", e) for e in errs]
        return 1
    out = a.out or (a.root / "jobs" / job.id / "out" / "final.mp4")
    print(build(job, a.root, out, a.encoder, not a.no_grain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
