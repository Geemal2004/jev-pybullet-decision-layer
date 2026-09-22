"""Diagnose: where (true-x) do out_of_reach errors live? Boundary cluster or spread?"""
from main import run_episode
import json, os
from logger import PATH

if os.path.exists(PATH):
    os.remove(PATH)
for s in range(15):
    run_episode(seed=1000 + s * 4 + 2, scenario="out_of_reach", verbose=False,
                noise_std=0.015, occ_prob=0.15)
rows = [json.loads(l) for l in open(PATH) if json.loads(l)["scenario"] == "out_of_reach"]
bad = [r for r in rows if not r["correct"]]
print(f"oor steps={len(rows)} bad={len(bad)}")
import collections
hist = collections.Counter()
for r in rows:
    tb = (r.get("true_blocks") or {}).get("red", [None])[0]
    if tb is None:
        continue
    band = f"{int(tb * 20) * 0.05:.2f}-{int(tb * 20) * 0.05 + 0.05:.2f}"
    hist[(band, "BAD" if r in bad else "ok")] += 1
for k in sorted(hist):
    print(f" true_red_x {k[0]} {k[1]}: {hist[k]}")
bx = [(r.get("true_blocks") or {}).get("red", [None])[0] for r in bad]
bx = [x for x in bx if x is not None]
print(f"bad true_red_x: min={min(bx):.3f} max={max(bx):.3f} within 0.75-0.85: {sum(1 for x in bx if 0.75 <= x <= 0.85)}/{len(bx)}")
