"""Standing habit: whenever a second stochastic source is added, prove independence
before trusting any combined number. Fails loudly if toggling occlusion changes jitter draws."""
from perception import to_jev_state
from sim_env import SimEnv
import random

def test_independence():
    env = SimEnv()
    gt = env.reset(seed=42, scenario="out_of_reach")
    a = to_jev_state(gt, None, None, noise_std=0.015, occ_prob=0.0,
                     rng_jitter=random.Random("j-42-0-0.015"), rng_occ=random.Random("o-42-0-0.0"))
    b = to_jev_state(gt, None, None, noise_std=0.015, occ_prob=0.15,
                     rng_jitter=random.Random("j-42-0-0.015"), rng_occ=random.Random("o-42-0-0.15"))
    assert a["blocks"]["red"]["xyz"] == b["blocks"]["red"]["xyz"], "jitter stream contaminated by occ toggle"
    assert a["ee_xyz"] == b["ee_xyz"], "ee jitter contaminated by occ toggle"
    # occlusion stream alone must be reproducible too
    c = to_jev_state(gt, None, None, noise_std=0.0, occ_prob=0.15,
                     rng_jitter=random.Random("j-42-0-0.0"), rng_occ=random.Random("o-42-0-0.15"))
    assert b["occluded"] == c["occluded"], "occ stream contaminated by jitter toggle"
    print("independence OK: jitter independent of occlusion")
    env.close()


def test_force_independence():
    """Third stream (force sensor): must not move with jitter/occlusion toggles, and must
    not perturb them."""
    env = SimEnv()
    gt = env.reset(seed=42, scenario="std_slip")
    def st(ns, op):
        return to_jev_state(gt, None, None, noise_std=ns, occ_prob=op,
                            rng_jitter=random.Random(f"j-42-0-{ns}"), rng_occ=random.Random(f"o-42-0-{op}"),
                            rng_force=random.Random("f-42-0"))
    a, b = st(0.0, 0.0), st(0.015, 0.15)
    assert a["gripper_force_N"] == b["gripper_force_N"], "force stream contaminated by jitter/occ"
    assert a["wrist_load_N"] == b["wrist_load_N"], "load stream contaminated by jitter/occ"
    base = to_jev_state(env.reset(seed=42, scenario="out_of_reach"), None, None, noise_std=0.015,
                        rng_jitter=random.Random("j-42-0-0.015"), rng_occ=random.Random("o-42-0-0.0"))
    shift_gt = env.reset(seed=42, scenario="std_normal")
    shift = to_jev_state(shift_gt, None, None, noise_std=0.015,
                         rng_jitter=random.Random("j-42-0-0.015"), rng_occ=random.Random("o-42-0-0.0"),
                         rng_force=random.Random("f-42-0"))
    assert base["blocks"]["blue"]["xyz"] == shift["blocks"]["blue"]["xyz"], "force stream perturbed jitter"
    assert "grasp_unstable" not in a, "shift suite leaked the grasp_unstable flag"
    print("independence OK: force sensor independent of jitter/occlusion; no flag leak")
    env.close()

if __name__ == "__main__":
    test_independence()
    test_force_independence()
