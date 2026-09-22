"""Jev call: single POST with all questions in parallel. Never per control tick."""
import os, json, urllib.request
from config import MODEL

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"

def decide(state, questions, model=MODEL, timeout=30):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return _mock(state, questions, reason="no_key")
    payload = {"model": model, "state": state, "questions": questions}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "jev-robot/0.1"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        return {"answers": body["answers"], "usage": body.get("usage", {}), "mock": False}
    except Exception as e:
        return _mock(state, questions, reason=str(e)[:200])

def _mock(state, questions, reason=""):
    # deterministic fallback so sim/eval runs offline
    holding = state.get("holding")
    ans = {}
    if "next_skill" in questions:
        skill = "place" if holding else "pick"
        ans["next_skill"] = {"type": "choice", "choice": skill,
            "confidence": 0.85, "probabilities": {"pick": 0.5 if not holding else 0.1, "place": 0.5 if holding else 0.1,
            "push": 0.05, "regrasp": 0.05, "wait": 0.2}}
    if "grasp_stable" in questions:
        ans["grasp_stable"] = {"type": "noul", "noul": 0.8 if holding else 0.05}
    if "placed_correctly" in questions:
        ans["placed_correctly"] = {"type": "noul", "noul": 0.1}
    if "risk" in questions:
        ans["risk"] = {"type": "score", "score": 0.5, "confidence": 0.6,
                       "probabilities": {"0": 0.6, "1": 0.3, "2": 0.1, "3": 0.0}}
    if "feasibility" in questions:
        ans["feasibility"] = {"type": "score", "score": 1.5, "confidence": 0.6,
                       "probabilities": {"0": 0.2, "1": 0.3, "2": 0.5}}
    return {"answers": ans, "usage": {}, "mock": True, "reason": reason}
