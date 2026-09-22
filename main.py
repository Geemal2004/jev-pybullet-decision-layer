"""One episode: perceive -> Jev (1 call, all questions) -> supervise -> act."""
from sim_env import SimEnv
from perception import to_jev_state
from config import QUESTIONS
from decision import decide
from supervisor import gate
import policy, logger
from oracle import oracle_skill, oracle_set

def _reachable(xyz):
    # unified with sim WORKSPACE (x 0.2-0.8, y +-0.4): matches physics clamp in move_ee
    return 0.2 <= xyz[0] <= 0.8 and abs(xyz[1]) <= 0.4

def _unplaced(gt):
    out = []
    for b, v in gt["blocks"].items():
        tgt = gt["bins"][v["target_bin"]]["xyz"]
        if abs(v["xyz"][0] - tgt[0]) > 0.05 or abs(v["xyz"][1] - tgt[1]) > 0.05:
            out.append(b)
    return out

def _pick_target(gt):
    # pick => nearest REACHABLE unplaced block (deterministic downstream of skill)
    cands = [b for b in _unplaced(gt) if _reachable(gt["blocks"][b]["xyz"])]
    if not cands:
        return None
    ee = gt["ee_xyz"]
    return min(cands, key=lambda b: sum((a - c) ** 2 for a, c in zip(ee, gt["blocks"][b]["xyz"])))

def _push_target(gt):
    # push => the out-of-reach unplaced block (deterministic downstream of skill)
    for b in _unplaced(gt):
        if not _reachable(gt["blocks"][b]["xyz"]):
            return b
    return None

def run_episode(seed=0, scenario="normal", max_steps=8, verbose=True, noise_std=0.0, occ_prob=0.0, use_breaker=True, on_step=None):
    import random
    env = SimEnv()
    gt = env.reset(seed, scenario=scenario)
    last_action, last_outcome, retries = None, None, 0
    stagnant = 0  # consecutive steps with zero physical progress (clean GT blocks+holding identical)
    prev_sig = None
    STAGNANT_PUSH_AFTER = 2  # then force deterministic push of the out-of-reach block
    for step in range(max_steps):
        gt = env.get_ground_truth()
        sig = (tuple(sorted((b, tuple(v["xyz"])) for b, v in gt["blocks"].items())), gt["holding"])
        if prev_sig is not None and sig == prev_sig:
            stagnant += 1
        else:
            stagnant = 0
        prev_sig = sig
        # separate streams: jitter draws identical whether occ is on or off (attribution-safe)
        rng_j = random.Random(f"j-{seed}-{step}-{noise_std}")
        rng_o = random.Random(f"o-{seed}-{step}-{occ_prob}")
        state = to_jev_state(gt, last_action, last_outcome, noise_std=noise_std, occ_prob=occ_prob, rng_jitter=rng_j, rng_occ=rng_o)
        res = decide(state, QUESTIONS)
        answers = res["answers"]
        gate_res = gate(state, answers, retries)
        action = gate_res["action"]
        # stagnation breaker: N no-progress steps with an out-of-reach block waiting
        # => deterministic recovery push (policy-level, not a Jev question)
        force_push = None
        if use_breaker and stagnant >= STAGNANT_PUSH_AFTER:
            force_push = _push_target(gt)
            if force_push is not None:
                action = "push"
                gate_res = {"action": "push", "reason": f"stagnant_{stagnant}_force_push_{force_push}"}
        oset = oracle_set(gt, state.get("occluded", []))
        oracle = oracle_skill(gt, state.get("occluded", []))
        outcome = {"ok": True}
        if action == "abort":
            last_action = "abort"
            break
        elif action == "pick":
            bid = _pick_target(gt)
            if bid is None:
                outcome = policy.do_wait(env)
                last_action = "wait (no reachable target)"
            else:
                outcome = policy.do_pick(env, bid)
                last_action = f"pick {bid}"
        elif action == "place":
            if gt["holding"]:
                tgt_bin = gt["blocks"][gt["holding"]]["target_bin"]
                outcome = policy.do_place(env, tgt_bin)
                last_action = f"place {tgt_bin}"
            else:
                outcome = policy.do_wait(env)
                last_action = "wait"
        elif action == "push":
            bid = _push_target(gt)
            if bid is None:
                bid = _pick_target(gt)  # nothing unreachable; nudge nearest unplaced
                if bid is None:
                    outcome = policy.do_wait(env)
                    last_action = "wait (nothing to push)"
                else:
                    outcome = policy.do_push(env, bid)
                    last_action = f"push {bid}"
            else:
                outcome = policy.do_push(env, bid)
                last_action = f"push {bid}"
        elif action == "regrasp":
            outcome = policy.do_regrasp(env)
            last_action = "regrasp"
        else:
            outcome = policy.do_wait(env)
            last_action = "wait"
        last_outcome = outcome
        retries = retries + 1 if not outcome.get("ok") else 0
        rec = {"seed": seed, "scenario": scenario, "step": step,
               "oracle": oracle, "oracle_set": sorted(oset),
               "correct": answers.get("next_skill", {}).get("choice") in oset,
               "gate": gate_res,
               "pred": answers.get("next_skill", {}).get("choice"),
               "conf": answers.get("next_skill", {}).get("confidence"),
               "risk": answers.get("risk", {}).get("score"),
               "risk_conf": answers.get("risk", {}).get("confidence"),
               "feas": answers.get("feasibility", {}).get("score"),
               "feas_conf": answers.get("feasibility", {}).get("confidence"),
                "mock": res.get("mock", False), "outcome": outcome,
                "occluded": state.get("occluded", []),
                "noise_std": noise_std, "occ_prob": occ_prob,
                "true_blocks": {b: [round(c, 3) for c in v["xyz"]] for b, v in gt["blocks"].items()},
                "seen_blocks": {b: v["xyz"] for b, v in state.get("blocks", {}).items()},
                "seen_reachable": state.get("reachable", {}),
                "dropped": env.dropped, "collision": env.collision,
                "unstable": gt.get("grasp_unstable", False)}
        logger.log(rec)
        if on_step is not None:
            on_step({"gt": gt, "state": state, "answers": answers, "rec": rec,
                     "seed": seed, "scenario": scenario, "step": step,
                     "noise_std": noise_std, "occ_prob": occ_prob})
        if verbose:
            print(f"[{scenario}] step {step} oracle={oracle} pred={rec['pred']} conf={rec['conf']} risk={rec['risk']} feas={rec['feas']} gate={gate_res} outcome={outcome}")
        if oracle == "wait" and not gt["holding"]:
            break
    env.close()
    return True

if __name__ == "__main__":
    run_episode(scenario="normal")
