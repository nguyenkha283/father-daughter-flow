"""Cay mot tin hieu vao so lieu gia lap, xem report co tim ra khong."""
import sys, sqlite3, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import metrics, schema

metrics.DB = ROOT / "tests" / "_tmp" / "m.sqlite"
metrics.DB.parent.mkdir(parents=True, exist_ok=True)
metrics.DB.unlink(missing_ok=True)
metrics.ROOT = ROOT

# --- test 1: features() doc dung job that ---
job = schema.load(ROOT / "jobs/example.yaml")
f = metrics.features(job)
print("features(example.yaml):")
for k, v in f.items(): print(f"    {k:16s} {v}")
exp = [("n_shots", 8), ("n_i2v", 3), ("hook_lane", "i2v"),
       ("hook_dur", 1.5), ("n_motifs", 6), ("season", "nom"), ("has_mother", 0)]
ok1 = all(f[k] == v for k, v in exp)
print("  => " + ("PASS features dung" if ok1 else f"FAIL {f}"))

# --- test 2: so lieu gia lap, co cay tin hieu ---
# Tin hieu cay vao: nhip lang cuoi >= 10s thi % xem het cao hon ~12 diem.
rnd = random.Random(5)
con = metrics.db()
for i in range(24):
    long_rest = i % 2 == 0
    rest = 11.0 if long_rest else 5.0
    pct = (58 if long_rest else 46) + rnd.uniform(-4, 4)
    jid = f"job{i:02d}"
    con.execute("INSERT INTO videos VALUES (?,?,?,?)",
                (f"vid{i:02d}", jid, f"Video {i}", "2026-10-01"))
    con.execute("INSERT INTO features VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (jid, 8, 34.0, 0.62, 3, "i2v" if i % 3 else "parallax",
                 1.5, rest, 2, 5, ["nom","he","thu"][i%3],
                 ["chieu_vang","dem"][i%2], i % 4 == 0))
    con.execute("INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?)",
                (f"vid{i:02d}", "2026-11-01", int(rnd.uniform(800, 9000)),
                 pct, pct*0.34, int(pct*3), int(pct), int(pct/6)))
con.commit()

print("\n" + "="*62)
class A: pass
metrics.cmd_report(A())
print("="*62)

rep = (ROOT / "metrics-report.md").read_text(encoding="utf-8")
ok2 = "rest_dur" in rep and "nhip lang cuoi" in rep
ok3 = "24 video" in rep
ok4 = "doan mo" not in rep          # n=24 >= 10 nen khong duoc canh bao thieu du lieu
print(f"\n  {'PASS' if ok2 else 'FAIL'}  tim ra tin hieu da cay (rest_dur)")
print(f"  {'PASS' if ok3 else 'FAIL'}  dem dung so video")
print(f"  {'PASS' if ok4 else 'FAIL'}  khong canh bao thieu du lieu khi n=24")
(ROOT / "metrics-report.md").unlink(missing_ok=True)
sys.exit(0 if all([ok1, ok2, ok3, ok4]) else 1)
