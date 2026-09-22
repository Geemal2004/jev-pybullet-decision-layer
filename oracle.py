"""Oracle as SETS of acceptable actions — recovery has multiple valid paths."""
def _in_bin(block_xyz, bin_xyz, tol=0.05):
    return abs(block_xyz[0] - bin_xyz[0]) < tol and abs(block_xyz[1] - bin_xyz[1]) < tol

def oracle_set(gt, occluded=None):
    """Return set of acceptable next skills. Accuracy = pred in set.
    occluded = block ids hidden from Jev this step (logged from state). When a
    REQUIRED (unplaced, unheld) block is occluded, wait joins the set: acting
    blind is not required, holding for observation is valid caution."""
    holding = gt.get("holding")
    unstable = gt.get("grasp_unstable", False)
    if holding and unstable:
        return {"regrasp"}  # placing now drops; push impossible while holding
    if holding:
        return {"place"}
    # not holding: physical facts only (no scenario tag — eval metadata must not leak into ground truth)
    unplaced = [bid for bid, b in gt["blocks"].items() if not _in_bin(b["xyz"], gt["bins"][b["target_bin"]]["xyz"])]
    if not unplaced:
        return {"wait"}
    out_of_reach = [bid for bid in unplaced
                    if gt["blocks"][bid]["xyz"][0] > 0.8 or abs(gt["blocks"][bid]["xyz"][1]) > 0.4]
    reachable = [bid for bid in unplaced if bid not in out_of_reach]
    if out_of_reach and reachable:
        # both orderings complete the task: push-red-first or pick-blue-first
        base = {"push", "pick"}
    elif out_of_reach:
        base = {"push"}
    else:
        base = {"pick"}
    occ = set(occluded or [])
    if occ & set(unplaced):
        base = set(base) | {"wait"}
    return base

def oracle_skill(gt, occluded=None):
    s = oracle_set(gt, occluded)
    # canonical for display: prefer place > regrasp > push > pick > wait
    for c in ["place", "regrasp", "push", "pick", "wait"]:
        if c in s:
            return c
    return "wait"
