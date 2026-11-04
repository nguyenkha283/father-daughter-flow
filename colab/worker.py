"""
Worker chay TREN COLAB T4. Doc inbox/batch.json tu Drive, sinh keyframe + clip i2v,
ghi ra outbox/ kem co 'done' cho tung shot.

NGUYEN TAC SONG CON: moi shot duoc checkpoint rieng. Colab Free SE bi ngat.
Chay lai notebook la no bo qua shot da xong va di tiep. Khong bao gio lam lai tu dau.

LUU Y PHAN CUNG: T4 la Turing — KHONG co bfloat16, KHONG co FlashAttention-2.
Moi thu phai fp16. Dung bf16 se loi hoac cham kinh khung.
"""
from __future__ import annotations

import gc, json, subprocess, time
from pathlib import Path

import torch

# --- cau hinh -------------------------------------------------------------- #
SDXL = "stabilityai/stable-diffusion-xl-base-1.0"
LTX = "Lightricks/LTX-Video"

# SDXL co "bucket" do phan giai da train san. 768x1344 la bucket 9:16 chuan;
# sinh dung bucket roi phong len 832x1472 cho ket qua on dinh hon nhieu so voi
# ep SDXL sinh thang o kich thuoc la.
GEN_W, GEN_H = 768, 1344
OUT_W, OUT_H = 832, 1472

# LTX doi kich thuoc chia het cho 32 va so frame dang 8n+1.
I2V_W, I2V_H = 512, 896
I2V_FPS = 24
OUT_FPS = 30

STYLE_SUFFIX = ", cozyhn_style, 2d animation, soft warm light, paper grain texture"
NEG_DEFAULT = ("photo, 3d render, text, watermark, extra fingers, deformed hands, "
               "harsh shadow, oversaturated, horror, blurry")


def _free():
    gc.collect()
    torch.cuda.empty_cache()


def _frames_for(sec: float) -> int:
    n = int(round(sec * I2V_FPS))
    return max(9, ((n - 1) // 8) * 8 + 1)      # ep ve dang 8k+1


# --- giai doan 1: keyframe -------------------------------------------------- #
def gen_stills(batch, outbox: Path, loras: dict[str, tuple[str, float]]):
    from diffusers import StableDiffusionXLPipeline

    todo = [(b, it) for b in batch for it in b["items"] if it["need_still"]]
    todo = [(b, it) for b, it in todo
            if not (outbox / b["job"] / "stills" / f"{it['shot']}.png").exists()]
    if not todo:
        print("[stills] khong con gi de lam"); return
    print(f"[stills] {len(todo)} keyframe")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        SDXL, torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    pipe.enable_model_cpu_offload()        # bat buoc tren T4 16GB
    pipe.enable_vae_slicing()

    names = []
    for key, (path, w) in loras.items():
        pipe.load_lora_weights(path, adapter_name=key); names.append((key, w))
    if names:
        pipe.set_adapters([n for n, _ in names], [w for _, w in names])

    for i, (b, it) in enumerate(todo, 1):
        dst = outbox / b["job"] / "stills" / f"{it['shot']}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        img = pipe(prompt=it["prompt"] + STYLE_SUFFIX,
                   negative_prompt=it.get("negative") or NEG_DEFAULT,
                   width=GEN_W, height=GEN_H, num_inference_steps=30,
                   guidance_scale=6.0,
                   generator=torch.Generator("cuda").manual_seed(it["seed"])).images[0]
        img.resize((OUT_W, OUT_H)).save(dst)   # checkpoint = file ton tai
        print(f"  [{i}/{len(todo)}] {b['job']}/{it['shot']}  {time.time()-t0:.0f}s")

    del pipe; _free()


# --- giai doan 2: image-to-video -------------------------------------------- #
def gen_i2v(batch, inbox: Path, outbox: Path):
    from diffusers import LTXImageToVideoPipeline
    from diffusers.utils import export_to_video
    from PIL import Image

    todo = [(b, it) for b in batch for it in b["items"] if it["need_i2v"]]
    todo = [(b, it) for b, it in todo
            if not (outbox / b["job"] / "clips" / f"{it['shot']}.mp4").exists()]
    if not todo:
        print("[i2v] khong con gi de lam"); return
    print(f"[i2v] {len(todo)} clip")

    pipe = LTXImageToVideoPipeline.from_pretrained(LTX, torch_dtype=torch.float16)
    pipe.enable_model_cpu_offload()

    for i, (b, it) in enumerate(todo, 1):
        src = (outbox / b["job"] / "stills" / f"{it['shot']}.png")
        if not src.exists():
            src = inbox / b["job"] / "stills" / f"{it['shot']}.png"
        if not src.exists():
            print(f"  bo qua {it['shot']}: khong co keyframe"); continue

        dst = outbox / b["job"] / "clips" / f"{it['shot']}.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".raw.mp4")
        t0 = time.time()
        frames = pipe(image=Image.open(src).convert("RGB").resize((I2V_W, I2V_H)),
                      prompt=it["prompt"] + STYLE_SUFFIX,
                      negative_prompt=it.get("negative") or NEG_DEFAULT,
                      width=I2V_W, height=I2V_H,
                      num_frames=_frames_for(it["duration"]),
                      num_inference_steps=40,
                      generator=torch.Generator("cuda").manual_seed(it["seed"])).frames[0]
        export_to_video(frames, str(tmp), fps=I2V_FPS)

        # phong ve 832x1472, doi fps, cat dung thoi luong -> ghi de nguyen tu
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                        "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos,fps={OUT_FPS}",
                        "-t", f"{it['duration']:.3f}", "-an",
                        "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
                        str(dst)], check=True)
        tmp.unlink(missing_ok=True)
        print(f"  [{i}/{len(todo)}] {b['job']}/{it['shot']}  {time.time()-t0:.0f}s")

    del pipe; _free()


def main(bridge: str = "/content/drive/MyDrive/father-and-daughter",
         lora_dir: str | None = None):
    bridge_p = Path(bridge)
    inbox, outbox = bridge_p / "inbox", bridge_p / "outbox"
    batch = json.loads((inbox / "batch.json").read_text(encoding="utf-8"))
    print(f"batch: {len(batch)} job, "
          f"{sum(len(b['items']) for b in batch)} shot can xu ly\n")

    loras = {}
    if lora_dir:
        ld = Path(lora_dir)
        for key, w in (("dad", 0.8), ("girl", 0.8), ("style", 0.6)):
            f = ld / f"lora_{key}.safetensors"
            if f.exists():
                loras[key] = (str(f), w)
        print("LoRA nap:", list(loras) or "KHONG CO (dang chay base model)")

    t0 = time.time()
    gen_stills(batch, outbox, loras)    # nap SDXL -> giai phong
    gen_i2v(batch, inbox, outbox)       # roi moi nap LTX
    print(f"\nXONG trong {(time.time()-t0)/60:.1f} phut. "
          f"Chay lai notebook se bo qua phan da xong.")


if __name__ == "__main__":
    main()
