"""Schema cua mot job video + luat cua World Bible duoi dang kiem tra duoc."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

# --- Hang so lay thang tu WORLD-BIBLE.md ------------------------------------
SETS = ["ban_cong", "bep_ban_an", "phong_khach", "phong_moonie",
        "phong_bo_me", "nha_tam", "hanh_lang", "goc_lam_viec"]
SEASONS = ["dong", "nom", "he", "thu"]
TIMES = ["tomo_sang", "nang_trua", "chieu_vang", "hoang_hon", "dem"]
MOTIFS = ["coc_sut", "tho_bong", "chieu_truc", "ghe_nhua_do", "quat_cay",
          "chuong_gio", "dep_to_ong", "chau_hung_que", "khan_sua", "nam_cham"]
CHARACTERS = ["father", "moonie", "mother"]
BEATS = ["hook", "body", "rest", "end"]
LANES = ["parallax", "i2v"]

MIN_DUR, MAX_DUR = 30.0, 60.0
MIN_MOTIFS = 3
MIN_PARALLAX_SHARE = 0.60   # muc 13.4: GPU la tai nguyen khan hiem
HOOK_MAX = 1.8              # muc 8: hook phai xong truoc 1.5-1.8s
REST_MIN = 8.0              # muc 8: nhip lang cuoi it nhat 8s
W, H, FPS = 832, 1472, 30
XFADE = 0.6      # chuyen canh, dung chung voi assemble.py


@dataclass
class Shot:
    id: str
    beat: str
    set: str
    prompt: str
    lane: str = "parallax"
    move: str = "static"
    duration: float = 4.0
    seed: int = 0
    motifs: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    negative: str = ""


@dataclass
class Job:
    id: str
    title: str
    logline: str
    season: str
    time: str
    shots: list[Shot] = field(default_factory=list)
    music: str = ""
    ambient: list[str] = field(default_factory=list)
    target_lufs: float = -14.0
    publish: dict[str, Any] = field(default_factory=dict)

    # -- dan xuat --
    @property
    def duration(self) -> float:
        """Thoi luong THAT tren timeline: xfade an bot (n-1)*XFADE giay."""
        if not self.shots:
            return 0.0
        return round(sum(s.duration for s in self.shots)
                     - (len(self.shots) - 1) * XFADE, 2)

    @property
    def raw_duration(self) -> float:
        return round(sum(s.duration for s in self.shots), 2)

    @property
    def motifs(self) -> set[str]:
        return {m for s in self.shots for m in s.motifs}

    @property
    def parallax_share(self) -> float:
        if not self.shots:
            return 0.0
        return sum(1 for s in self.shots if s.lane == "parallax") / len(self.shots)

    @property
    def i2v_shots(self) -> list[Shot]:
        return [s for s in self.shots if s.lane == "i2v"]

    def dir(self, root: Path) -> Path:
        return root / "jobs" / self.id


def load(path: Path) -> Job:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    shots = [Shot(**s) for s in raw.pop("shots", [])]
    return Job(shots=shots, **raw)


def save(job: Job, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(asdict(job), allow_unicode=True, sort_keys=False),
        encoding="utf-8")


# --- Validator --------------------------------------------------------------
def validate(job: Job) -> list[str]:
    """Tra ve danh sach loi. Rong = dat. Day la World Bible duoi dang code."""
    e: list[str] = []

    if not job.shots:
        return ["job khong co shot nao"]

    if not (MIN_DUR <= job.duration <= MAX_DUR):
        e.append(f"tong thoi luong {job.duration}s ngoai khoang "
                 f"{MIN_DUR}-{MAX_DUR}s")

    if job.season not in SEASONS:
        e.append(f"season '{job.season}' khong hop le, phai thuoc {SEASONS}")
    if job.time not in TIMES:
        e.append(f"time '{job.time}' khong hop le, phai thuoc {TIMES}")

    ids = [s.id for s in job.shots]
    if len(ids) != len(set(ids)):
        e.append("co shot id trung nhau")

    for s in job.shots:
        if s.set not in SETS:
            e.append(f"{s.id}: set '{s.set}' khong nam trong 8 set co dinh")
        if s.beat not in BEATS:
            e.append(f"{s.id}: beat '{s.beat}' khong hop le")
        if s.lane not in LANES:
            e.append(f"{s.id}: lane '{s.lane}' khong hop le")
        if s.duration <= 0:
            e.append(f"{s.id}: duration phai > 0")
        for m in s.motifs:
            if m not in MOTIFS:
                e.append(f"{s.id}: motif '{m}' khong co trong World Bible")
        for c in s.characters:
            if c not in CHARACTERS:
                e.append(f"{s.id}: nhan vat '{c}' khong ton tai")
        if not s.prompt.strip():
            e.append(f"{s.id}: thieu prompt")

    # Muc 8 — cau truc 3 nhip
    first = job.shots[0]
    if first.beat != "hook":
        e.append("shot dau tien phai co beat 'hook'")
    elif first.duration > HOOK_MAX:
        e.append(f"hook dai {first.duration}s, phai <= {HOOK_MAX}s")

    rest_shots = [s for s in job.shots if s.beat in ("rest", "end")]
    rest = sum(s.duration for s in rest_shots) - max(0, len(rest_shots) - 1) * XFADE
    if rest < REST_MIN:
        e.append(f"nhip lang cuoi chi {rest}s, phai >= {REST_MIN}s "
                 "(day la cho cam xuc dong lai, dung cat)")
    if job.shots[-1].beat not in ("rest", "end"):
        e.append("shot cuoi phai la beat 'rest' hoac 'end'")

    # Muc 5 — it nhat 3 dao cu motif
    if len(job.motifs) < MIN_MOTIFS:
        e.append(f"chi co {len(job.motifs)} dao cu motif, can >= {MIN_MOTIFS}")

    # Muc 13.4 — ti le lane
    if job.parallax_share < MIN_PARALLAX_SHARE:
        e.append(f"ti le parallax {job.parallax_share:.0%} < "
                 f"{MIN_PARALLAX_SHARE:.0%}; qua nhieu shot i2v se vo ngan sach T4")

    # Muc 1 — tieu diem cha-con
    has_f = any("father" in s.characters for s in job.shots)
    has_m = any("moonie" in s.characters for s in job.shots)
    if not (has_f and has_m):
        e.append("video phai co ca father va moonie xuat hien")
    if "mother" in {c for s in job.shots for c in s.characters}:
        last_chars = job.shots[-1].characters
        if "mother" in last_chars and len(last_chars) > 1:
            pass
        if not ({"father", "moonie"} <= set(last_chars)):
            e.append("co mother thi shot cuoi phai quay ve cha-con "
                     "(muc 1: tieu diem khong duoc dich chuyen)")
    return e


def warnings(job: Job) -> list[str]:
    """Khong chan publish, nhung nen xem lai."""
    w = []
    n_i2v = len(job.i2v_shots)
    if n_i2v > 4:
        w.append(f"{n_i2v} shot i2v — ngan sach T4 tinh tren 3-4 shot/video")
    if n_i2v == 0:
        w.append("khong co shot i2v nao; video co the thieu chuyen dong that")
    if job.shots[0].lane != "i2v":
        w.append("hook dang dung parallax; hook thuong manh hon neu la i2v")
    if len({s.set for s in job.shots}) < 2:
        w.append("ca video chi dien ra o 1 set, de don dieu")
    return w
