"""Non-Jev deciders for the with/without comparison. Each returns answers in the
same shape as decision.decide(), so the supervisor, stagnation breaker, target
selection and motion primitives stay identical -- only the decision source changes.

fixed      Blind pick/place loop: alternates pick -> place until it has placed every
           block once, then waits. Reads only `holding`. The "no judgment" robot.
rules      Hand-written reactive rules over the SAME perceived (noisy/occluded) state
           Jev sees. In the shift suite, grasp stability is a grip-force threshold
           tuned on the standard block only (wood, 0.10 kg).
rules_eng  Shift suite only: rules plus an engineered friction model and material
           table. Catches unseen materials/masses; cannot read operator notes.
"""
from grasp_physics import MATERIALS, TRANSPORT_FACTOR

# Standard-block data: stable grasps read ~6 N, poor grasps ~0.9 N. Any threshold
# in (1.5, 5) N separates them perfectly there; 3.0 is the midpoint choice.
STANDARD_GRIP_THRESHOLD_N = 3.0


def _answers(skill):
    # neutral signals: risk 0 never blocks, feasibility 2 never redirects
    return {
        "next_skill": {"type": "choice", "choice": skill, "confidence": 1.0},
        "risk": {"type": "score", "score": 0.0},
        "feasibility": {"type": "score", "score": 2.0},
    }


def _in_bin(bxyz, binxyz, tol=0.05):
    return abs(bxyz[0] - binxyz[0]) < tol and abs(bxyz[1] - binxyz[1]) < tol


def _mean(xs):
    return sum(xs) / len(xs)


class FixedSequence:
    name = "fixed"

    def __init__(self, n_blocks):
        self.n_blocks = n_blocks
        self.placed = 0

    def decide(self, state):
        if state["holding"]:
            self.placed += 1
            return _answers("place")
        if self.placed >= self.n_blocks:
            return _answers("wait")
        return _answers("pick")


class ReactiveRules:
    name = "rules"

    def __init__(self, n_blocks):
        pass

    def grasp_unstable(self, state):
        if "grasp_unstable" in state:
            return state["grasp_unstable"]
        return _mean(state["gripper_force_N"]) < STANDARD_GRIP_THRESHOLD_N

    def decide(self, state):
        if state["holding"]:
            return _answers("regrasp" if self.grasp_unstable(state) else "place")
        unplaced = [b for b, v in state["blocks"].items()
                    if not _in_bin(v["xyz"], state["bins"][v["target_bin"]]["xyz"])]
        if any(state["reachable"].get(b) for b in unplaced):
            return _answers("pick")
        if unplaced:
            return _answers("push")
        return _answers("wait")


class EngineeredRules(ReactiveRules):
    name = "rules_eng"

    def grasp_unstable(self, state):
        mu = MATERIALS[state["held_material"]]
        capacity = 2 * mu * _mean(state["gripper_force_N"])
        return TRANSPORT_FACTOR * _mean(state["wrist_load_N"]) > capacity


DECIDERS = {"fixed": FixedSequence, "rules": ReactiveRules, "rules_eng": EngineeredRules}
