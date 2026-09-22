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

if __name__ == "__main__":
    test_independence()
