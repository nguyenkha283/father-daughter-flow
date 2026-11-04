"""Validator phai BAT duoc vi pham, khong chi pass job dung."""
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import schema

BASE = schema.load(Path(__file__).resolve().parents[1] / "jobs/example.yaml")


def mutate(fn):
    j = copy.deepcopy(BASE); fn(j); return schema.validate(j)


def hit(errs, frag):
    return any(frag in e for e in errs)


CASES = [
    ("job chuan khong co loi",
     lambda j: None, None),
    ("hook dai qua 1.8s",
     lambda j: setattr(j.shots[0], "duration", 4.0), "hook dai"),
    ("thieu nhip lang cuoi",
     lambda j: [setattr(s, "beat", "body") for s in j.shots[-2:]], "nhip lang"),
    ("shot dau khong phai hook",
     lambda j: setattr(j.shots[0], "beat", "body"), "beat 'hook'"),
    ("set khong co trong World Bible",
     lambda j: setattr(j.shots[2], "set", "quan_ca_phe"), "8 set co dinh"),
    ("motif bia ra",
     lambda j: setattr(j.shots[1], "motifs", ["xe_may"]), "khong co trong World Bible"),
    ("duoi 3 dao cu motif",
     lambda j: [setattr(s, "motifs", []) for s in j.shots[1:]], "dao cu motif"),
    ("qua nhieu i2v, vo ngan sach T4",
     lambda j: [setattr(s, "lane", "i2v") for s in j.shots], "vo ngan sach T4"),
    ("video dai qua 60s",
     lambda j: [setattr(s, "duration", 12.0) for s in j.shots[1:]], "ngoai khoang"),
    ("thieu Moonie",
     lambda j: [setattr(s, "characters", ["father"]) for s in j.shots], "father va moonie"),
    ("co mother nhung shot cuoi khong quay ve cha-con",
     lambda j: setattr(j.shots[-1], "characters", ["mother"]), "quay ve cha-con"),
    ("season bia ra",
     lambda j: setattr(j, "season", "xuan"), "season"),
    ("shot id trung",
     lambda j: setattr(j.shots[3], "id", "shot_02"), "trung nhau"),
    ("prompt rong",
     lambda j: setattr(j.shots[4], "prompt", "   "), "thieu prompt"),
]

ok = True
for name, fn, expect in CASES:
    errs = mutate(fn)
    good = (not errs) if expect is None else hit(errs, expect)
    ok &= good
    print(("  PASS  " if good else "  FAIL  ") + name)
    if not good:
        print("        -> ", errs[:3])
print("\n=> " + ("TAT CA PASS" if ok else "CO CHECK FAIL"))
sys.exit(0 if ok else 1)
