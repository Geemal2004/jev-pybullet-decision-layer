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

# Shift suite: no grasp_unstable flag. Stability must be judged from the force
# sensor, the block material and the operator note. Criteria say WHAT matters,
# never the formula or any threshold.
QUESTIONS_SHIFT = {
    **QUESTIONS,
    "next_skill": {
        "type": "choice",
        "instructions": ("Choose the safest next skill given gripper, block and bin positions, "
                         "the gripper force sensor (gripper_force_N = grip squeeze, wrist_load_N = "
                         "weight of held block), block materials, and the operator_note if any. "
                         "If all_placed is true and gripper is empty, choose wait."),
        "criteria": {
            "pick": "Gripper empty, not all_placed, and a block is reachable outside its bin.",
            "place": ("Gripper holds a block with enough grip to carry it without slipping "
                      "(grip force and surface friction comfortably exceed what its weight "
                      "demands during motion), and its target bin is safe to use now."),
            "push": "Gripper empty and a block is out of reach for direct pick.",
            "regrasp": ("Gripper holds a block whose grip may not survive transport "
                        "(too little squeeze for its weight and surface); regrasp firms the grip."),
            "wait": ("all_placed true with empty gripper, or the operator_note or state makes "
                     "acting now unsafe."),
        },
    },
    "grasp_stable": {
        "type": "noul",
        "instructions": ("Will the held block survive transport without slipping, given grip force, "
                         "wrist load, material, and any operator_note about the block's surface?"),
        "criteria": {"true": "Grip comfortably exceeds what weight and surface friction demand",
                     "false": "Empty gripper, weak grip, or heavy/slippery block for this grip"},
    },
    "risk": {
        "type": "score",
        "instructions": ("Score DANGER only: collision/drop potential of moving now (insufficient "
                         "grip for the load and surface, a person working in the target bin per "
                         "the operator_note, fast motion near bins). Ignore reachability."),
        "criteria": ["Low", "Moderate", "High", "Critical"],
    },
}

MODEL = "typesafe/jev-1.13"
