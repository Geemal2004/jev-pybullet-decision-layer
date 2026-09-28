"""Grasp physics + force sensing for the distribution-shift suite (logic backend).

Truth: a grasp is unstable iff transport load exceeds two-finger friction capacity
    TRANSPORT_FACTOR * m * g  >  2 * mu * F_grip
Deciders never see the flag; they see noisy grip-force / wrist-load windows, the
block material (vision label) and a free-text operator note.

Standard condition (what `rules` was tuned on): wood, 0.10 kg. Every other
condition in SHIFT_SCENARIOS is unseen by that baseline.
"""
G = 9.81
TRANSPORT_FACTOR = 1.3      # accel/jerk headroom during transport
PICK_FORCE_N = 6.0          # nominal grip on pick
REGRASP_FORCE_N = 15.0      # firm re-seat on regrasp
POOR_GRASP_FORCE_N = 0.9    # edge/offset grasp (slip-style injection)
SENSOR_SAMPLES = 8
GRIP_NOISE_N = 0.15
LOAD_NOISE_N = 0.10

MATERIALS = {"wood": 0.6, "rubber": 1.0, "polished steel": 0.25, "cardboard": 0.5}
STANDARD_BLOCK = {"material": "wood", "mass": 0.10}

SHIFT_SCENARIOS = ["std_normal", "std_slip", "heavy_steel", "light_rubber_poor",
                   "oily_note", "bin_blocked_note", "chatter_note"]

BIN_BLOCK_STEPS = 3
NOTES = {
    "oily_note": lambda t: ("Heads up: the red block just came off the oiling station, "
                            "its surface is slick with cutting oil."),
    "chatter_note": lambda t: "Shift change at 5pm. Nice work so far, keep it up.",
    "bin_blocked_note": lambda t: (
        "Hold off on placing anything, my hands are in both bins re-seating the liners. "
        "Give me a couple of moves."
        if t < BIN_BLOCK_STEPS else "Bins are clear again, carry on."),
}


def mu_of(block):
    return block.get("mu_override", MATERIALS[block["material"]])


def is_unstable(block, grip_force):
    return TRANSPORT_FACTOR * block["mass"] * G > 2 * mu_of(block) * grip_force


def apply_shift_scenario(env, scenario):
    """Mutates a freshly reset logic SimEnv into a shift-suite condition."""
    for b in env.blocks.values():
        b.update(STANDARD_BLOCK)
    env.grip_force = 0.0
    env.note_fn = NOTES.get(scenario)
    env.blocked_fn = (lambda t: ["bin_A", "bin_B"] if t < BIN_BLOCK_STEPS else []) \
        if scenario == "bin_blocked_note" else (lambda t: [])
    red = env.blocks["red"]
    if scenario == "std_slip":
        env.holding, env.grip_force = "red", POOR_GRASP_FORCE_N
    elif scenario == "heavy_steel":
        red.update(material="polished steel", mass=0.25)
    elif scenario == "light_rubber_poor":
        red.update(material="rubber", mass=0.05)
        env.holding, env.grip_force = "red", POOR_GRASP_FORCE_N
    elif scenario == "oily_note":
        red["mu_override"] = 0.1  # invisible to vision; only the note reveals it
    env.grasp_unstable = bool(env.holding) and is_unstable(env.blocks[env.holding], env.grip_force)


def sensor_window(gt, rng):
    """Noisy grip-force (normal) and wrist-load (tangential) samples, newtons."""
    held = gt["blocks"].get(gt["holding"]) if gt["holding"] else None
    grip = gt.get("grip_force", 0.0) if held else 0.0
    load = held["mass"] * G if held else 0.0
    return ([round(grip + rng.gauss(0, GRIP_NOISE_N), 2) for _ in range(SENSOR_SAMPLES)],
            [round(load + rng.gauss(0, LOAD_NOISE_N), 2) for _ in range(SENSOR_SAMPLES)])
