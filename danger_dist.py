"""Danger threshold distribution: drop-positives (probes) vs clean states (main loop)."""
import json
from sim_env import SimEnv
from perception import to_jev_state
from config import QUESTIONS
from decision import decide
import policy

def run_probes(n=20):
    ds = []
    for seed in range(n):
        env = SimEnv()
        env.reset(seed=2000 + seed, scenario="slip")
        state = to_jev_state(env.get_ground_truth(), "probe", None)
        res = decide(state, QUESTIONS)
        d = res["answers"].get("risk", {}).get("score")
        out = policy.do_place(env, "bin_A")
        assert out.get("reason") == "drop_unstable_grasp"
        ds.append(d)
        env.close()
    return [x for x in ds if x is not None]

def pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]

if __name__ == "__main__":
    pos = run_probes(20)
    rows = [json.loads(l) for l in open("runs.jsonl")]
    # clean = steps with ok outcomes (no drop/unreachable), danger score present
    neg = [r["risk"] for r in rows if (r.get("outcome") or {}).get("ok") and r.get("risk") is not None]
    print(f"positives (pre-drop) n={len(pos)} min={min(pos):.2f} p10={pct(pos,0.1):.2f} p50={pct(pos,0.5):.2f} max={max(pos):.2f}")
    print(f"negatives (clean steps) n={len(neg)} min={min(neg):.2f} p50={pct(neg,0.5):.2f} p90={pct(neg,0.9):.2f} max={max(neg):.2f}")
    for thr in (1.0, 1.5, 1.75, 2.0):
        tpr = sum(1 for x in pos if x >= thr) / max(1, len(pos))
        fpr = sum(1 for x in neg if x >= thr) / max(1, len(neg))
        print(f" thr={thr}: TPR={tpr:.2f} FPR={fpr:.2f}")
