"""Eval: set-accuracy + calibration by scenario + risk-vs-failure. Run: python eval.py [n_per] [noise_std] [occ_prob]"""
from main import run_episode
from sim_env import SCENARIOS
import json, os, sys
from logger import PATH

def evaluate(n_per=10, noise_std=0.0, occ_prob=0.0):
    if os.path.exists(PATH):
        os.remove(PATH)
    total_eps = 0
    for i in range(n_per):
        for sc in SCENARIOS:
            run_episode(seed=1000 + total_eps, scenario=sc, verbose=False, noise_std=noise_std, occ_prob=occ_prob)
            total_eps += 1
    rows = [json.loads(l) for l in open(PATH)]
    real = [r for r in rows if not r.get("mock")]
    acc = sum(1 for r in rows if r["correct"]) / max(1, len(rows))
    print(f"episodes={total_eps} ({n_per}/scenario) noise_std={noise_std} occ_prob={occ_prob} decisions={len(rows)} live_jev={len(real)} set_acc={acc:.2f}")
    print("--- calibration overall ---")
    for lo, hi in [(0.0, 0.7), (0.7, 0.85), (0.85, 1.01)]:
        b = [r for r in rows if r.get("conf") is not None and lo <= r["conf"] < hi]
        a = sum(1 for r in b if r["correct"]) / len(b) if b else 0
        print(f" conf {lo}-{hi}: n={len(b)} acc={a:.2f}")
    print("--- by scenario (conf bucket x scenario) ---")
    for sc in SCENARIOS + ["done_step"]:
        sub = [r for r in rows if (r["scenario"] == sc or (sc == "done_step" and r["oracle"] == "wait"))]
        if not sub:
            continue
        a = sum(1 for r in sub if r["correct"]) / len(sub)
        print(f" {sc}: n={len(sub)} set_acc={a:.2f}")
        for lo, hi in [(0.0, 0.7), (0.7, 1.01)]:
            b = [r for r in sub if r.get("conf") is not None and lo <= r["conf"] < hi]
            if b:
                ba = sum(1 for r in b if r["correct"]) / len(b)
                print(f"   conf {lo}-{hi}: n={len(b)} acc={ba:.2f}")
    print("--- danger (risk) vs drop only: per-step outcome.reason ---")
    danger_bad = [r for r in rows if (r.get("outcome") or {}).get("reason") == "drop_unstable_grasp"]
    danger_good = [r for r in rows if r not in danger_bad and r.get("risk") is not None]
    db = [r["risk"] for r in danger_bad if r.get("risk") is not None]
    dg = [r["risk"] for r in danger_good if r.get("risk") is not None]
    print(f" danger positives (drop)={len(danger_bad)} (expect 0 in main loop; positives live in probe_danger.py)")
    if dg:
        print(f" main-loop avg_risk={sum(dg)/len(dg):.2f} (slip-regrasp steps should elevate this)")
    print("--- feasibility vs unreachable only: per-step outcome.reason ---")
    feas_bad = [r for r in rows if (r.get("outcome") or {}).get("reason") == "unreachable"]
    feas_good = [r for r in rows if r not in feas_bad and r.get("feas") is not None]
    fb = [r["feas"] for r in feas_bad if r.get("feas") is not None]
    fg = [r["feas"] for r in feas_good if r.get("feas") is not None]
    print(f" feasibility positives (unreachable)={len(feas_bad)} avg_feas_bad={sum(fb)/max(1,len(fb)):.2f} avg_feas_good={sum(fg)/max(1,len(fg)):.2f}")
    print("--- risk (legacy, all failures) vs checkable failure ---")
    bad = [r for r in rows if (r.get("outcome") or {}).get("reason") in ("drop_unstable_grasp", "unreachable")]
    good = [r for r in rows if r not in bad and r.get("risk") is not None]
    bad_r = [r["risk"] for r in bad if r.get("risk") is not None]
    good_r = [r["risk"] for r in good if r.get("risk") is not None]
    if bad_r or good_r:
        print(f" failure_steps={len(bad)} avg_risk_bad={sum(bad_r)/max(1,len(bad_r)):.2f} avg_risk_good={sum(good_r)/max(1,len(good_r)):.2f}")
        # risk threshold check: P(failure | risk>=2) vs P(failure | risk<2)
        for thr in (1.5, 2.0):
            hi_r = [r for r in rows if (r.get("risk") or 0) >= thr]
            lo_r = [r for r in rows if (r.get("risk") or 0) < thr]
            p_hi = sum(1 for r in hi_r if r in bad) / max(1, len(hi_r))
            p_lo = sum(1 for r in lo_r if r in bad) / max(1, len(lo_r))
            print(f"  risk>={thr}: P(fail)={p_hi:.2f} (n={len(hi_r)}) vs risk<{thr}: P(fail)={p_lo:.2f} (n={len(lo_r)})")
    waits = [r for r in rows if r["gate"]["action"] == "wait"]
    print(f"wait_rate={len(waits)/max(1,len(rows)):.2f} n_waits={len(waits)}")
    occ_steps = [r for r in rows if r.get("occluded")]
    holds = [r for r in occ_steps if r.get("pred") == "wait"]
    print(f"cautious_hold: occluded_steps={len(occ_steps)} pred_wait={len(holds)} rate={len(holds)/max(1,len(occ_steps)):.2f} (wait now in oracle set when required block hidden)")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    ns = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    op = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    evaluate(n, ns, op)
