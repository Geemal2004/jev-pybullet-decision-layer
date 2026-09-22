"""Dumb perception: ground truth -> Jev state (structured JSON + short text)."""

WORKSPACE = {"x": (0.2, 0.8), "y": (-0.4, 0.4), "z": (0.0, 0.6)}

def _reachable(xyz):
    return (WORKSPACE["x"][0] <= xyz[0] <= WORKSPACE["x"][1]
            and WORKSPACE["y"][0] <= xyz[1] <= WORKSPACE["y"][1]
            and WORKSPACE["z"][0] <= xyz[2] <= WORKSPACE["z"][1])

def to_jev_state(gt, last_action=None, last_outcome=None, noise_std=0.0, occ_prob=0.0, rng=None, rng_jitter=None, rng_occ=None):
    """noise_std>0 jitters what JEV SEES (blocks + ee) with seeded Gaussian.
    occ_prob>0 randomly hides a block from Jev (OCCLUDED tag) with seeded RNG.
    Jitter and occlusion use SEPARATE streams so toggling one never changes the
    other's draws. Oracle/policy always use clean gt — noise never leaks."""
    import copy
    noisy_blocks = copy.deepcopy(gt["blocks"])
    noisy_ee = list(gt["ee_xyz"])
    import random
    rj = rng_jitter or rng or random
    ro = rng_occ or rng or random
    if noise_std > 0:
        for b in noisy_blocks.values():
            b["xyz"] = [c + rj.gauss(0, noise_std) for c in b["xyz"]]
        noisy_ee = [c + rj.gauss(0, noise_std) for c in noisy_ee]
    occluded = []
    if occ_prob > 0:
        for bid in list(noisy_blocks):
            if bid == gt.get("holding"):
                continue  # gripper knows what it holds; vision loss hits unheld blocks
            if ro.random() < occ_prob:
                occluded.append(bid)
                del noisy_blocks[bid]
    def _in_bin(bxyz, binxyz, tol=0.05):
        return abs(bxyz[0] - binxyz[0]) < tol and abs(bxyz[1] - binxyz[1]) < tol
    if noisy_blocks:
        all_placed = all(_in_bin(noisy_blocks[bid]["xyz"], gt["bins"][noisy_blocks[bid]["target_bin"]]["xyz"]) for bid in noisy_blocks)
    else:
        all_placed = False  # nothing seen != done
    reachable = {bid: _reachable(b["xyz"]) for bid, b in noisy_blocks.items()}
    # NOTE: scenario label deliberately excluded — model sees only physical facts,
    # otherwise it anchors on the eval tag instead of actual reachability.
    lines = [f"ee={noisy_ee} holding={gt['holding']} grasp_unstable={gt.get('grasp_unstable', False)} all_placed={all_placed}"]
    for bid, b in noisy_blocks.items():
        lines.append(f"block {bid} at {[round(c,3) for c in b['xyz']]} reachable={reachable[bid]} -> {b['target_bin']}")
    for bid in occluded:
        lines.append(f"block {bid} OCCLUDED (not visible)")
    state = {
        "ee_xyz": [round(c, 3) for c in noisy_ee],
        "holding": gt["holding"],
        "grasp_unstable": gt.get("grasp_unstable", False),
        "all_placed": all_placed,
        "blocks": {bid: {"xyz": [round(c, 3) for c in b["xyz"]], "target_bin": b["target_bin"]} for bid, b in noisy_blocks.items()},
        "bins": gt["bins"],
        "reachable": reachable,
        "workspace": WORKSPACE,
        "noise_std": noise_std,
        "occluded": occluded,
        "human_in_zone": gt.get("human_in_zone", False),
        "last_action": last_action,
        "last_outcome": last_outcome,
        "summary": "; ".join(lines),
    }
    return state
