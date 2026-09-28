"""With/without comparison: same seeds, same supervisor/breaker/motion, only the
decision source differs.
Run: python compare.py [n_per] [noise_std] [occ_prob] [backend] [deciders] [suite]
     python compare.py 15 0.0 0.0 logic fixed,rules,jev
     python compare.py 5 0.0 0.0 logic fixed,rules,rules_eng,jev shift
suite "base"  = the original four scenarios (grasp_unstable handed over as a flag).
suite "shift" = grasp_physics.SHIFT_SCENARIOS (force sensing, unseen materials/masses,
                operator notes; logic backend only).
Episode-level metrics (what a viewer sees), not per-step set accuracy:
success = every block in its target bin at episode end, gripper empty."""
import json
import os
import sys

from main import run_episode
from sim_env import SCENARIOS
from grasp_physics import SHIFT_SCENARIOS

HERE = os.path.dirname(__file__)
SUITES = {"base": SCENARIOS, "shift": SHIFT_SCENARIOS}


def compare(n_per=15, noise_std=0.0, occ_prob=0.0, backend="logic",
            deciders=("fixed", "rules", "jev"), suite="base"):
    if "jev" in deciders and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("OPENROUTER_API_KEY not set: jev would silently run the offline mock. "
                 "Set the key or drop 'jev' from the decider list.")
    if suite == "shift" and backend != "logic":
        sys.exit("shift suite is implemented on the logic backend only.")
    if "rules_eng" in deciders and suite != "shift":
        sys.exit("rules_eng needs the shift suite's force sensing.")
    scenarios = SUITES[suite]
    episodes = []
    for d in deciders:
        for i in range(n_per):
            for j, sc in enumerate(scenarios):
                seed = 1000 + i * len(scenarios) + j  # same seed schedule as eval.py
                ep = run_episode(seed=seed, scenario=sc, verbose=False,
                                 noise_std=noise_std, occ_prob=occ_prob,
                                 backend=backend, decider=d)
                if ep["mock_decisions"]:
                    # fail fast: a mixed live/mock table is unusable and nothing is saved
                    sys.exit(f"ABORTED: seed {seed} ({sc}) had {ep['mock_decisions']} Jev "
                             "decisions fall back to the offline mock (API error or "
                             "credits exhausted). No results written. See the "
                             "'mock_reason' field of mock records in runs.jsonl.")
                episodes.append(ep)

    print(f"suite={suite} backend={backend} noise_std={noise_std} occ_prob={occ_prob} "
          f"episodes/decider={n_per * len(scenarios)}")
    header = (f"{'scenario':<19}{'decider':<11}{'success':>8}{'drops':>7}{'unsafe':>8}"
              f"{'regrasp':>9}{'unreach':>9}{'aborts':>8}{'waits':>7}{'steps':>7}")
    print(header)
    print("-" * len(header))
    for sc in list(scenarios) + ["ALL"]:
        for d in deciders:
            sub = [e for e in episodes if e["decider"] == d and (sc == "ALL" or e["scenario"] == sc)]
            n = len(sub)
            print(f"{sc:<19}{d:<11}"
                  f"{sum(e['success'] for e in sub) / n:>8.2f}"
                  f"{sum(e['drops'] for e in sub):>7}"
                  f"{sum(e['safety_violations'] for e in sub):>8}"
                  f"{sum(e['regrasps'] for e in sub):>9}"
                  f"{sum(e['unreachable_attempts'] for e in sub):>9}"
                  f"{sum(e['aborted'] for e in sub):>8}"
                  f"{sum(e['waits'] for e in sub):>7}"
                  f"{sum(e['steps'] for e in sub) / n:>7.1f}")
        print()

    out = os.path.join(HERE, f"compare_{suite}_{backend}_n{noise_std}_o{occ_prob}_x{n_per}_{'-'.join(deciders)}.json")
    with open(out, "w") as f:
        json.dump({"suite": suite, "backend": backend, "noise_std": noise_std, "occ_prob": occ_prob,
                   "n_per": n_per, "deciders": list(deciders), "episodes": episodes}, f, indent=1)
    print(f"saved {out}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    ns = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    op = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    be = sys.argv[4] if len(sys.argv) > 4 else "logic"
    ds = tuple(sys.argv[5].split(",")) if len(sys.argv) > 5 else ("fixed", "rules", "jev")
    su = sys.argv[6] if len(sys.argv) > 6 else "base"
    compare(n, ns, op, be, ds, su)
