"""Supervisor owns safety, not Jev. Per-skill thresholds: recovery actions are
cheap/reversible so they pass at lower conf; risk blocks only progress actions."""
CONF_BY_SKILL = {"pick": 0.7, "place": 0.7, "push": 0.25, "regrasp": 0.5, "wait": 0.0}
RISK_BLOCK = 1.5  # danger threshold from probe distribution (TPR 1.00, FPR 0.05); blocks pick/place only
FEAS_PUSH = 1.2  # if last pick failed unreachable and feasibility low, redirect pick->push
MAX_RETRIES = 3

def gate(state, answers, retries):
    if state.get("human_in_zone"):
        return {"action": "wait", "reason": "human_in_zone"}
    if retries >= MAX_RETRIES:
        return {"action": "abort", "reason": "max_retries"}
    nxt = answers.get("next_skill", {})
    conf = nxt.get("confidence", 0)
    skill = nxt.get("choice", "wait")
    risk = answers.get("risk", {}).get("score", 0)
    feas = answers.get("feasibility", {}).get("score", 2)
    if skill in ("pick", "place") and risk >= RISK_BLOCK:
        return {"action": "wait", "reason": f"risk_{risk:.2f}_blocks_{skill}"}
    # feasibility redirect: repeated unreachable evidence + low feas => push, not another pick
    last_out = state.get("last_outcome") or {}
    if skill == "pick" and last_out.get("reason") == "unreachable" and feas is not None and feas < FEAS_PUSH:
        return {"action": "push", "reason": f"feas_{feas:.2f}_redirect_pick_to_push"}
    if conf < CONF_BY_SKILL.get(skill, 0.7):
        return {"action": "wait", "reason": f"low_conf_{conf:.2f}_skill_{skill}"}
    return {"action": skill, "reason": f"conf_{conf:.2f}"}
