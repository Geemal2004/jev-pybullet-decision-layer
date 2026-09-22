"""Scripted motion primitives — deterministic; unstable grasp drops on place."""
def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

def do_pick(env, block_id):
    b = env.blocks.get(block_id)
    if not b or env.holding:
        return {"ok": False, "reason": "no_block_or_hands_full"}
    env.move_ee([b["xyz"][0], b["xyz"][1], 0.15])
    env.move_ee(b["xyz"])
    if _dist(env.ee, b["xyz"]) < 0.05:
        env.holding = block_id
        env.grasp_unstable = False
        return {"ok": True}
    return {"ok": False, "reason": "unreachable"}

def do_place(env, bin_id):
    if not env.holding or bin_id not in env.bins:
        return {"ok": False, "reason": "nothing_to_place_or_bad_bin"}
    if env.grasp_unstable:
        # checkable failure: placing with unstable grasp drops the block
        bid = env.holding
        env.blocks[bid]["xyz"] = [env.ee[0], env.ee[1], 0.025]
        env.holding = None
        env.grasp_unstable = False
        env.dropped = True
        return {"ok": False, "reason": "drop_unstable_grasp", "dropped": bid}
    tgt = env.bins[bin_id]["xyz"]
    env.move_ee([tgt[0], tgt[1], 0.25])
    bid = env.holding
    env.blocks[bid]["xyz"] = [tgt[0], tgt[1], 0.025]
    env.holding = None
    return {"ok": True, "placed": bid}

def do_push(env, block_id):
    b = env.blocks.get(block_id)
    if not b:
        return {"ok": False}
    # nudge toward workspace center so a later pick can reach it
    b["xyz"][0] = max(0.45, b["xyz"][0] - 0.15)
    b["xyz"][1] = min(0.15, max(-0.15, b["xyz"][1]))
    env.move_ee([b["xyz"][0], b["xyz"][1], 0.15])
    return {"ok": True, "pushed": block_id}

def do_regrasp(env):
    if not env.holding:
        return {"ok": False, "reason": "empty_gripper"}
    env.grasp_unstable = False
    return {"ok": True, "regrasped": env.holding}

def do_wait(env):
    return {"ok": True, "waited": True}
