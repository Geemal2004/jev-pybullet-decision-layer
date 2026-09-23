"""Real out_of_reach-only battery with solvable-subset split. Seeds match the oor
slots of the 60-seed harness (total_eps % 4 == 2)."""
from main import run_episode
import json, os
from logger import PATH

N = 15
if os.path.exists(PATH):
    os.remove(PATH)
seeds = [1000 + i for i in range(60) if i % 4 == 2]
for s in seeds:
    run_episode(seed=s, scenario="out_of_reach", verbose=False, backend="real")
rows = [json.loads(l) for l in open(PATH)]
live = sum(1 for r in rows if not r.get("mock"))
acc = sum(1 for r in rows if r["correct"]) / len(rows)
imm = [r for r in rows if "immovable" in r["gate"].get("reason", "")]
imm_eps = {r["seed"] for r in imm}
solv = [r for r in rows if r["seed"] not in imm_eps]
print(f"real oor-only: eps={len(seeds)} decisions={len(rows)} live={live} acc={acc:.2f}")
print(f" immovable_abort episodes={len(imm_eps)}/{len(seeds)}")
if solv:
    print(f" solvable_subset: n={len(solv)} acc={sum(1 for r in solv if r['correct'])/len(solv):.2f}")
ab = sum(1 for r in rows if (r.get("outcome") or {}).get("reason") == "abort" or r["gate"]["action"] == "abort")
print(f" abort_gate_actions={ab}")
