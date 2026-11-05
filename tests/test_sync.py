"""State phai doi chieu voi dia, va push-final phai chan job chua san sang."""
import contextlib, io, sys, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import schema, state, sync

JOB = schema.load(ROOT / "jobs/example.yaml")
JDIR = ROOT / "jobs" / JOB.id
IDS = [s.id for s in JOB.shots]
ok = True

# --- 1. reconcile: co 'done' ma mat file thi phai bi xoa ---
st = state.State(JDIR / "state.json")
st.reconcile(IDS, JDIR)
victim = JDIR / "clips" / f"{IDS[2]}.mp4"
assert victim.exists(), "can chay tests/test_e2e.py truoc"
backup = victim.read_bytes()
st.mark(IDS[2], "clip")
before = st.has(IDS[2], "clip")
victim.unlink()                                   # gia lap don dia / sync xoa nham
cleared = st.reconcile(IDS, JDIR)
after = st.has(IDS[2], "clip")
victim.write_bytes(backup); st.mark(IDS[2], "clip")

for name, good in [("truoc khi xoa file: state = done", before),
                   ("sau khi xoa file: state khong con done", not after),
                   ("reconcile bao dung artifact bi mat",
                    cleared == [f"{IDS[2]}/clip"])]:
    print(("  PASS  " if good else "  FAIL  ") + name); ok &= good

# --- 2. reconcile phai mo lai cac stage phu thuoc ---
st.mark_stage("assemble"); st.mark_stage("qc")
victim.unlink(); st.reconcile(IDS, JDIR); victim.write_bytes(backup)
good = st.stage("assemble") == "pending" and st.stage("qc") == "pending"
print(("  PASS  " if good else "  FAIL  ") + "mat clip thi assemble/qc mo lai"); ok &= good
st.mark(IDS[2], "clip")

# --- 3. push-final: 3 truong hop ---
def push(label):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sync.push_final(dry=True, job_path=ROOT / "jobs/example.yaml")
    return "day len 1 job" in buf.getvalue()

st.mark_stage("qc", "pending")
a = push("qc chua dat")
st.mark_stage("qc", "done")
b = push("enabled=false")
p = ROOT / "jobs/example.yaml"; bak = p.read_text(encoding="utf-8")
d = yaml.safe_load(bak); d["publish"]["enabled"] = True
p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
c = push("du dieu kien")
p.write_text(bak, encoding="utf-8")

for name, good in [("chan job qc chua dat", not a),
                   ("chan job publish.enabled=false", not b),
                   ("cho qua job du dieu kien", c)]:
    print(("  PASS  " if good else "  FAIL  ") + name); ok &= good

print("\n=> " + ("TAT CA PASS" if ok else "CO CHECK FAIL"))
sys.exit(0 if ok else 1)
