# Jev robot starting phase — decision points (corrected types)
# Jev only supports: noul (0-1), choice (label+probs+confidence), score (continuous+probs)

QUESTIONS = {
    "next_skill": {
        "type": "choice",
        "instructions": "Choose the safest next skill given gripper, block and bin positions. If all_placed is true and gripper is empty, choose wait.",
        "criteria": {
            "pick": "Gripper empty, not all_placed, and a block is reachable outside its bin.",
            "place": "Gripper holding a block stably (grasp_unstable false).",
            "push": "Gripper empty and a block is out of reach for direct pick.",
            "regrasp": "Gripper holds a block with grasp_unstable true; must regrasp before placing.",
            "wait": "all_placed true with empty gripper, or state is unsafe/ambiguous."
        },
    },
    "grasp_stable": {
        "type": "noul",
        "instructions": "Gripper is holding a block stably enough to transport?",
        "criteria": {"true": "Block firmly held, no slip reported", "false": "Empty gripper or slipping/offset grasp"},
    },
    "placed_correctly": {
        "type": "noul",
        "instructions": "Target block is inside its correct bin?",
        "criteria": {"true": "Block center within bin bounds", "false": "Block outside bin or in wrong bin"},
    },
    "risk": {
        "type": "score",
        "instructions": "Score DANGER only: collision/drop potential of moving now (unstable grasp, clutter, fast motion near bins). Ignore whether the target is reachable — that is feasibility, not danger.",
        "criteria": ["Low", "Moderate", "High", "Critical"],
    },
    "feasibility": {
        "type": "score",
        "instructions": "Score FEASIBILITY only: can the gripper geometrically reach and execute the next pick/place now? Low if target block is outside the workspace or unreachable; high if reachable.",
        "criteria": ["Infeasible", "Uncertain", "Feasible"],
    },
}

MODEL = "typesafe/jev-1.13"
