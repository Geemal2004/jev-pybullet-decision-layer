"""Real-physics skill execution (KUKA iiwa). SAME function names/signatures as
policy.py; outcomes succeed/fail on real contact and IK, not scripted distances."""
GRASP_TOL = 0.08  # closed-loop EE repeatability, not scripted exactness


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def do_pick(env, block_id):
    if block_id is None:
        return {"ok": False, "reason": "no_target"}
    b = env.blocks.get(block_id)
    if not b or env.holding:
        return {"ok": False, "reason": "no_block_or_hands_full"}
    env.move_ee([b["xyz"][0], b["xyz"][1], 0.18])
    # grasp hover: EE stays ABOVE the block top (0.05) — descending into the body
    # interpenetrates and the solver fights the grasp constraint (block left
    # behind / flung on release). 0.09 keeps dist-to-center < GRASP_TOL cleanly.
    env.move_ee([b["xyz"][0], b["xyz"][1], 0.09])
    env._sync_blocks()
    if _dist(env.ee_pos(), env.blocks[block_id]["xyz"]) < GRASP_TOL:
        env._attach(block_id)
        env.holding = block_id
        env.grasp_unstable = False
        env.move_ee([b["xyz"][0], b["xyz"][1], 0.25])
        return {"ok": True}
    env.move_ee([b["xyz"][0], b["xyz"][1], 0.25])
    return {"ok": False, "reason": "unreachable"}


def do_place(env, bin_id):
    if not env.holding or bin_id not in env.bins:
        return {"ok": False, "reason": "nothing_to_place_or_bad_bin"}
    bid = env.holding
    unstable = env.grasp_unstable
    tgt = env.bins[bin_id]["xyz"]
    env.move_ee([tgt[0], tgt[1], 0.25])
    if unstable:
        # tilted carry released at height: block tumbles, lands off-target
        env._detach()
        env.holding = None
        env.grasp_unstable = False
        env.dropped = True
        env._settle(120)
        env._sync_blocks()
        return {"ok": False, "reason": "drop_unstable_grasp", "dropped": bid}
    env.move_ee([tgt[0], tgt[1], 0.10])
    env._hold_still()  # zero arm velocity BEFORE release or placement drifts
    env._detach()
    env.holding = None
    env._settle(60)
    env.move_ee([tgt[0], tgt[1], 0.25])
    env._settle(120)
    env._sync_blocks()
    got = env.blocks[bid]["xyz"]
    if abs(got[0] - tgt[0]) < 0.05 and abs(got[1] - tgt[1]) < 0.05:
        return {"ok": True, "placed": bid}
    return {"ok": False, "reason": "missed_bin", "landed": [round(c, 3) for c in got]}


def do_push(env, block_id):
    """Shove along -x through the block. NOTE: link-6 collision is masked globally
    (else the wrist ejects grasped blocks on release) so it is restored here —
    an EE that cannot touch cannot push (measured dx=0.000 with mask on)."""
    import pybullet as p
    if block_id is None:
        return {"ok": False, "reason": "no_target"}
    b = env.blocks.get(block_id)
    if not b:
        return {"ok": False}
    p.setCollisionFilterGroupMask(env.arm, 6, 1, 1)
    try:
        # contact at block-mid height through its center line
        env.move_ee([b["xyz"][0] + 0.10, b["xyz"][1], 0.03])
        env.move_ee([b["xyz"][0] -0.14, b["xyz"][1], 0.03])
        env.move_ee([b["xyz"][0] - 0.14, b["xyz"][1], 0.20])
        env._settle(60)
        env._sync_blocks()
        return {"ok": True, "pushed": block_id}
    finally:
        p.setCollisionFilterGroupMask(env.arm, 6, 0, 0)


def do_regrasp(env):
    if not env.holding:
        return {"ok": False, "reason": "empty_gripper"}
    bid = env.holding
    env._sync_blocks()
    pos = env.blocks[bid]["xyz"]
    env.move_ee([pos[0], pos[1], 0.18])
    env._detach()
    env.holding = None
    env._settle(60)
    env.move_ee([pos[0], pos[1], 0.05])
    env._sync_blocks()
    if _dist(env.ee_pos(), env.blocks[bid]["xyz"]) < GRASP_TOL:
        env._attach(bid)  # centered this time
        env.holding = bid
        env.grasp_unstable = False
        env.move_ee([pos[0], pos[1], 0.25])
        return {"ok": True, "regrasped": bid}
    return {"ok": False, "reason": "regrasp_missed"}


def do_wait(env):
    env._settle(12)
    return {"ok": True, "waited": True}
