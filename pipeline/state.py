"""
State machine idempotent cho tung job.

Ly do ton tai: Colab Free SE bi ngat giua chung. Moi don vi cong viec nho nhat
(1 shot x 1 artifact) duoc danh dau rieng, nen chay lai bat cu stage nao cung
chi lam phan con thieu. Khong co lop nay thi pipeline khong song duoc tren T4.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

STAGES = ["brief", "stills", "depth", "animate", "assemble", "qc", "publish"]
ARTIFACTS = ["still", "depth", "clip"]


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"stages": {}, "shots": {}, "log": []}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    # -- ghi --
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.path)   # ghi nguyen tu, tranh state hong khi bi kill

    def mark_stage(self, stage: str, status: str = "done") -> None:
        assert stage in STAGES, stage
        self.data["stages"][stage] = status
        self._log(f"stage {stage} -> {status}")
        self.save()

    def mark(self, shot_id: str, artifact: str, status: str = "done") -> None:
        assert artifact in ARTIFACTS, artifact
        self.data["shots"].setdefault(shot_id, {})[artifact] = status
        self.save()

    def _log(self, msg: str) -> None:
        self.data["log"].append({"t": time.strftime("%Y-%m-%d %H:%M:%S"),
                                 "msg": msg})
        self.data["log"] = self.data["log"][-200:]

    # -- doc --
    def stage(self, stage: str) -> str:
        return self.data["stages"].get(stage, "pending")

    def has(self, shot_id: str, artifact: str) -> bool:
        return self.data["shots"].get(shot_id, {}).get(artifact) == "done"

    # -- doi chieu voi dia --
    @staticmethod
    def artifact_path(jdir: Path, shot_id: str, artifact: str) -> Path:
        return {
            "still": jdir / "stills" / f"{shot_id}.png",
            "depth": jdir / "depth" / f"{shot_id}.png",
            "clip": jdir / "clips" / f"{shot_id}.mp4",
        }[artifact]

    def reconcile(self, shot_ids: Iterable[str], jdir: Path) -> list[str]:
        """
        Xoa cac co 'done' ma file tuong ung khong con tren dia.

        State va dia co the lech nhau that: don dia, rclone sync xoa nham,
        hoac copy do dang. Neu khong doi chieu thi pipeline se skip buoc do
        roi chet o buoc sau voi mot loi kho hieu.
        """
        cleared = []
        for sid in shot_ids:
            for art in ARTIFACTS:
                if (self.data["shots"].get(sid, {}).get(art) == "done"
                        and not self.artifact_path(jdir, sid, art).exists()):
                    self.data["shots"][sid].pop(art, None)
                    cleared.append(f"{sid}/{art}")
        if cleared:
            self._log(f"reconcile: xoa co cho {len(cleared)} artifact mat file")
            for st in ("animate", "assemble", "qc", "publish"):
                self.data["stages"].pop(st, None)
            self.save()
        return cleared

    def todo(self, shot_ids: Iterable[str], artifact: str) -> list[str]:
        """Danh sach shot con thieu artifact nay. Day la ham quan trong nhat."""
        return [s for s in shot_ids if not self.has(s, artifact)]

    def progress(self, shot_ids: list[str]) -> dict[str, str]:
        out = {}
        for a in ARTIFACTS:
            done = sum(1 for s in shot_ids if self.has(s, a))
            out[a] = f"{done}/{len(shot_ids)}"
        return out

    def reset(self, stage: str | None = None, artifact: str | None = None):
        if stage:
            self.data["stages"].pop(stage, None)
        if artifact:
            for s in self.data["shots"].values():
                s.pop(artifact, None)
        self.save()
