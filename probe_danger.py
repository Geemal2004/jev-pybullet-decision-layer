"""Danger probes: force place-when-unstable, record danger score BEFORE the drop.
Gives true positives for the danger detector without contaminating main eval."""
from sim_env import SimEnv
from perception import to_jev_state
from config import QUESTIONS
from decision import decide
import policy

def run_probes(n=10):
    scored = []
    for seed in range(n):
        env = SimEnv()
        env.reset(seed=2000 + seed, scenario="slip")  # holding + unstable
        gt = env.get_ground_truth()
        state = to_jev_state(gt, "probe", None)
        res = decide(state, QUESTIONS)
        danger = res["answers"].get("risk", {}).get("score")
        feas = res["answers"].get("feasibility", {}).get("score")
        # force the dangerous action supervisor would block
        out = policy.do_place(env, "bin_A")
        dropped = out.get("reason") == "drop_unstable_grasp"
        scored.append((danger, feas, dropped))
        print(f"probe {seed}: danger={danger:.2f} feas={feas} dropped={dropped} mock={res.get('mock')}")
        env.close()
    ds = [d for d, f, dr in scored if d is not None]
    print(f"probes={n} drops={sum(1 for _,_,dr in scored if dr)} avg_danger_before_drop={sum(ds)/max(1,len(ds)):.2f} (expect >=2 if danger detector works)")

if __name__ == "__main__":
    run_probes()
