"""PyBullet scene + failure injection for recovery eval."""
try:
    import pybullet as p
    import pybullet_data
    _HAS_PB = True
except Exception:
    _HAS_PB = False

WORKSPACE = {"x": (0.2, 0.8), "y": (-0.4, 0.4), "z": (0.0, 0.6)}
SCENARIOS = ["normal", "slip", "out_of_reach", "wrong_bin"]

class SimEnv:
    def __init__(self, gui=False):
        self.gui = gui and _HAS_PB
        self.ee = [0.5, 0.0, 0.3]
        self.holding = None
        self.blocks = {}
        self.bins = {}
        self._pb_ids = {}
        self.grasp_unstable = False
        self.scenario = "normal"
        self.dropped = False
        self.collision = False
        if _HAS_PB:
            self.cid = p.connect(p.GUI if self.gui else p.DIRECT)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
        else:
            self.cid = None

    def reset(self, seed=0, scenario="normal"):
        import random
        rng = random.Random(seed)
        self.scenario = scenario
        self.grasp_unstable = False
        self.dropped = False
        self.collision = False
        self.blocks = {
            "red": {"xyz": [0.45 + rng.uniform(-0.05, 0.05), -0.15, 0.025], "target_bin": "bin_A", "size": 0.05},
            "blue": {"xyz": [0.55, 0.15, 0.025], "target_bin": "bin_B", "size": 0.05},
        }
        self.bins = {"bin_A": {"xyz": [0.65, -0.2, 0.0]}, "bin_B": {"xyz": [0.65, 0.2, 0.0]}}
        self.ee = [0.5, 0.0, 0.3]
        self.holding = None
        if scenario == "slip":
            # holding but unstable — must regrasp before place, else drop
            self.holding = "red"
            self.grasp_unstable = True
        elif scenario == "out_of_reach":
            # red pushed outside workspace — direct pick unreachable, needs push first
            self.blocks["red"]["xyz"] = [0.95, 0.38, 0.025]
        elif scenario == "wrong_bin":
            # red sitting in the wrong bin — must re-pick to correct bin
            wb = self.bins["bin_B"]["xyz"]
            self.blocks["red"]["xyz"] = [wb[0], wb[1], 0.025]
        if _HAS_PB:
            p.resetSimulation(physicsClientId=self.cid)
            p.setGravity(0, 0, -9.8, physicsClientId=self.cid)
            p.loadURDF("plane.urdf", physicsClientId=self.cid)
            self._pb_ids = {}
            for bid, b in self.blocks.items():
                self._pb_ids[bid] = p.loadURDF("cube_small.urdf", b["xyz"], physicsClientId=self.cid)
        return self.get_ground_truth()

    def get_ground_truth(self):
        return {
            "ee_xyz": list(self.ee),
            "holding": self.holding,
            "grasp_unstable": self.grasp_unstable,
            "scenario": self.scenario,
            "blocks": {k: {"xyz": list(v["xyz"]), "target_bin": v["target_bin"]} for k, v in self.blocks.items()},
            "bins": {k: {"xyz": list(v["xyz"])} for k, v in self.bins.items()},
            "human_in_zone": False,
        }

    def move_ee(self, xyz):
        # clamp; flag collision if target was outside workspace (checkable for risk eval)
        raw = list(xyz)
        if not (WORKSPACE["x"][0] <= raw[0] <= WORKSPACE["x"][1] and
                WORKSPACE["y"][0] <= raw[1] <= WORKSPACE["y"][1] and
                WORKSPACE["z"][0] <= raw[2] <= WORKSPACE["z"][1]):
            self.collision = True
        x = min(max(xyz[0], WORKSPACE["x"][0]), WORKSPACE["x"][1])
        y = min(max(xyz[1], WORKSPACE["y"][0]), WORKSPACE["y"][1])
        z = min(max(xyz[2], WORKSPACE["z"][0]), WORKSPACE["z"][1])
        self.ee = [x, y, z]
        if _HAS_PB:
            for _ in range(10):
                p.stepSimulation(physicsClientId=self.cid)

    def close(self):
        if _HAS_PB and self.cid is not None:
            p.disconnect(self.cid)
