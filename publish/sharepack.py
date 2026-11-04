"""
Sinh share pack cho Facebook Groups — phan BAN TU DONG.

Groups khong co API. Tu dong hoa bang cookie/browser la vi pham ToS va de
mat tai khoan. Nen he thong chuan bi san moi thu, con viec paste la cua ban:
toi da 3-5 group/ngay, moi group mot caption KHAC NHAU THAT.
"""
from __future__ import annotations
import difflib
from pathlib import Path

MAX_GROUPS_PER_DAY = 5
SIMILAR_LIMIT = 0.72    # tren nguong nay thi coi nhu copy-paste


def check_variants(variants: list[str]) -> list[str]:
    """Bat truong hop 'doi vai emoji roi goi la caption moi'."""
    warn = []
    if len(variants) < 3:
        warn.append(f"chi co {len(variants)} caption, nen co it nhat 3")
    for i in range(len(variants)):
        for j in range(i + 1, len(variants)):
            r = difflib.SequenceMatcher(None, variants[i], variants[j]).ratio()
            if r > SIMILAR_LIMIT:
                warn.append(f"caption #{i+1} va #{j+1} giong nhau {r:.0%} "
                            "— Facebook se coi la spam, viet lai")
    return warn


def build(job, video_url: str, cover: Path, out: Path,
          variants: list[str] | None = None) -> dict:
    variants = variants or (job.publish.get("facebook", {}) or {}).get("variants", [])
    warn = check_variants(variants)

    lines = [f"# Share pack — {job.title}", "",
             f"- Video: {video_url}", f"- Anh bia: `{cover}`",
             f"- Gioi han tu dat: **toi da {MAX_GROUPS_PER_DAY} group/ngay**", ""]
    if warn:
        lines += ["> **Canh bao truoc khi paste:**"] + [f"> - {w}" for w in warn] + [""]
    lines += ["Moi group mot caption rieng. Dung paste cung mot doan.", ""]
    for i, v in enumerate(variants, 1):
        lines += [f"## Caption {i}", "", "```", v.strip(), "```", ""]
    lines += ["---", "", "| # | Group | Gio goi y | Da dang |",
              "|---|-------|-----------|---------|"]
    for i in range(1, MAX_GROUPS_PER_DAY + 1):
        lines.append(f"| {i} |  | {7 + i*3:02d}:00 | [ ] |")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"out": str(out), "variants": len(variants), "warnings": warn}
