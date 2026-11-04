"""
End-to-end lane local: 8 clip -> ghep -> QC.
Dung canh gia lap thay cho keyframe SDXL (chua co GPU), moi khau con lai la that.
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import schema, assemble, qc, state
from pipeline.parallax import render

ROOT = Path(__file__).resolve().parents[1]
JOB = schema.load(ROOT / "jobs/example.yaml")
JDIR = ROOT / "jobs" / JOB.id
TMP = ROOT / "tests" / "_tmp"

MOVES = ["static", "drift_right", "drift_up", "push_in",
         "drift_left", "pull_out", "float", "static"]

st = state.State(JDIR / "state.json")
print(f"== job {JOB.id}  |  {len(JOB.shots)} shot  |  {JOB.duration}s ==\n")

t0 = time.time()
todo = st.todo([s.id for s in JOB.shots], "clip")
print(f"clip con thieu: {len(todo)}/{len(JOB.shots)}")
for s, mv in zip(JOB.shots, MOVES):
    if st.has(s.id, "clip"):
        print(f"  skip {s.id} (da co)"); continue
    render(TMP / "still.png", TMP / "depth.png",
           JDIR / "clips" / f"{s.id}.mp4", mv, s.duration)
    st.mark(s.id, "clip")
    print(f"  {s.id}  {mv:12s} {s.duration:4.1f}s")
st.mark_stage("animate")
print(f"-> {time.time()-t0:.1f}s\n")

print("== assemble ==")
t0 = time.time()
info = assemble.build(JOB, ROOT, JDIR / "out" / "final.mp4")
print(json.dumps(info, ensure_ascii=False), f"  ({time.time()-t0:.1f}s)\n")
st.mark_stage("assemble")

print("== QC ==")
res = qc.run(JDIR / "out" / "final.mp4", JOB, JDIR / "out" / "contact.jpg")
for c in res["checks"]:
    print(("  PASS  " if c["pass"] else "  FAIL  ") + f"{c['name']:32s} {c['value']}")
st.mark_stage("qc", "done" if res["pass"] else "needs_review")

print(f"\ncontact sheet: {res['contact_sheet']}")
print("state:", json.dumps(st.progress([s.id for s in JOB.shots])))
print("\n=> " + ("E2E PASS" if res["pass"] else "E2E FAIL"))
sys.exit(0 if res["pass"] else 1)
