"""Feasibility probes: step0 out_of_reach vs normal — is the signal still blind?"""
from sim_env import SimEnv
from perception import to_jev_state
from config import QUESTIONS
from decision import decide

def probe(scenario, n=10, seed_base=3000):
    fs = []
    for i in range(n):
        env = SimEnv()
        env.reset(seed=seed_base + i, scenario=scenario)
        state = to_jev_state(env.get_ground_truth(), None, None)
        res = decide(state, QUESTIONS)
        f = res["answers"].get("feasibility", {}).get("score")
        fs.append(f)
        env.close()
    fs = [x for x in fs if x is not None]
    return fs

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    oor = probe("out_of_reach", n, 3000)
    norm = probe("normal", n, 4000)
    print(f"out_of_reach step0 feas: n={len(oor)} avg={sum(oor)/len(oor):.2f} min={min(oor):.2f} max={max(oor):.2f}")
    print(f"normal step0 feas:      n={len(norm)} avg={sum(norm)/len(norm):.2f} min={min(norm):.2f} max={max(norm):.2f}")
    print("SEPARATED" if sum(oor)/len(oor) < sum(norm)/len(norm) - 0.3 else "STILL BLIND")
