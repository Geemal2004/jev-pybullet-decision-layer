"""Real-physics backend: KUKA iiwa + rigid bodies, SAME SimEnv API and GT schema
as sim_env.py. Decision/oracle/perception code is untouched by design —
only the world (this file) and skill execution (policy_real.py) are real."""
import pybullet as p
import pybullet_data

WORKSPACE = {"x": (0.2, 0.8), "y": (-0.4, 0.4), "z": (0.0, 0.6)}
SCENARIOS = ["normal", "slip", "out_of_reach", "wrong_bin"]
HOME = [0.5, 0.0, 0.3]
EE_LINK = 6
STEP_HZ = 240
# NOTE: no forced tool-down orientation — it stalls low IK on this arm (verified:
# down-quat hered to dist 0.062+, free orientation converges to 0.000). Grasp is by
# EE proximity + constraint, so orientation is irrelevant to the decision layer.


class SimEnv:
    def __init__(self, gui=False):
        self.gui = gui
        self.cid = p.connect(p.GUI if gui else p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        if gui:
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
            p.resetDebugVisualizerCamera(cameraDistance=1.6, cameraYaw=90,
                                         cameraPitch=-25,
                                         cameraTargetPosition=[0.55, 0, 0.1])
        p.setGravity(0, 0, -9.8)
        p.setPhysicsEngineParameter(fixedTimeStep=1.0 / STEP_HZ, numSolverIterations=50)
        self.arm = None
        self.blocks = {}
        self.bins = {}
        self._pb_ids = {}
        self._bin_ids = {}
        self.holding = None
        self.grasp_unstable = False
        self.scenario = "normal"
        self.dropped = False
        self.collision = False
        self.grasp_cid = None

    # ---- world building -------------------------------------------------
    def reset(self, seed=0, scenario="normal"):
        import random
        rng = random.Random(seed)
        self.scenario = scenario
        self.grasp_unstable = False
        self.dropped = False
        self.collision = False
        self.holding = None
        self.grasp_cid = None
        p.resetSimulation()
        p.setGravity(0, 0, -9.8)
        p.setPhysicsEngineParameter(fixedTimeStep=1.0 / STEP_HZ, numSolverIterations=50)
        p.loadURDF("plane.urdf")
        self.arm = p.loadURDF("kuka_iiwa/model.urdf", [0, 0, 0], useFixedBase=True)
        for j in range(7):
            p.resetJointState(self.arm, j, 0.0)  # neutral ready pose; IK converges from here
        # wrist must not shove the payload: its collision volume surrounds the EE
        # origin where the grasped block rides. Disabling link-6 contact kills a
        # pose-dependent ejection (block ending up UNDER the floor on release).
        p.setCollisionFilterGroupMask(self.arm, EE_LINK, 0, 0)
        self.blocks = {
            "red": {"xyz": [0.45 + rng.uniform(-0.05, 0.05), -0.15, 0.03], "target_bin": "bin_A"},
            "blue": {"xyz": [0.55, 0.15, 0.03], "target_bin": "bin_B"},
        }
        self.bins = {"bin_A": {"xyz": [0.65, -0.2, 0.0]}, "bin_B": {"xyz": [0.65, 0.2, 0.0]}}
        self._pb_ids = {}
        for bid, b in self.blocks.items():
            self._pb_ids[bid] = p.loadURDF("cube_small.urdf", b["xyz"])
            p.changeDynamics(self._pb_ids[bid], -1, lateralFriction=1.0,
                             spinningFriction=0.5, restitution=0.0, linearDamping=0.3)
        self._bin_ids = {}
        for bid, b in self.bins.items():
            tray = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.07, 0.07, 0.005])
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.07, 0.07, 0.005],
                                      rgbaColor=[0.75, 0.66, 0.45, 1])
            self._bin_ids[bid] = p.createMultiBody(baseMass=0, baseCollisionShapeIndex=tray,
                                                   baseVisualShapeIndex=vis,
                                                   basePosition=[b["xyz"][0], b["xyz"][1], 0.005])
        if scenario == "slip":
            self._attach("red", offset=[0.03, 0.0, 0.0])  # tilted carry
            self.holding = "red"
            self.grasp_unstable = True
        elif scenario == "out_of_reach":
            p.resetBasePositionAndOrientation(self._pb_ids["red"], [0.95, 0.38, 0.03], [0, 0, 0, 1])
        elif scenario == "wrong_bin":
            wb = self.bins["bin_B"]["xyz"]
            p.resetBasePositionAndOrientation(self._pb_ids["red"], [wb[0], wb[1], 0.03], [0, 0, 0, 1])
        self._settle(60)
        self._sync_blocks()
        return self.get_ground_truth()

    # ---- low-level helpers ----------------------------------------------
    def _step(self, n=12):
        for _ in range(n):
            p.stepSimulation()

    def _settle(self, n):
        self._step(n)

    def ee_pos(self):
        st = p.getLinkState(self.arm, EE_LINK, computeForwardKinematics=True)
        return list(st[4])

    def _ik(self, xyz):
        return p.calculateInverseKinematics(self.arm, EE_LINK, xyz)

    def _goto_joints(self, qs, steps=240, vel=2.5):
        for j, q in enumerate(qs[:7]):
            p.setJointMotorControl2(self.arm, j, p.POSITION_CONTROL, targetPosition=q,
                                    force=300, maxVelocity=vel)
        self._step(steps)

    def _hold_still(self, tol=0.05, max_rounds=10):
        # re-command current positions until joint velocities die (pre-release)
        for _ in range(max_rounds):
            qs = [p.getJointState(self.arm, j)[0] for j in range(7)]
            for j, q in enumerate(qs):
                p.setJointMotorControl2(self.arm, j, p.POSITION_CONTROL, targetPosition=q,
                                        force=300, maxVelocity=0.3)
            self._step(24)
            if max(abs(p.getJointState(self.arm, j)[1]) for j in range(7)) < tol:
                break

    def _goto_ee_closed_loop(self, xyz, tol=0.02, max_rounds=6):
        # fire-and-forget never converges on a 7DOF arm; iterate to tolerance
        for _ in range(max_rounds):
            self._goto_joints(self._ik(xyz), steps=200)
            if sum((a - b) ** 2 for a, b in zip(self.ee_pos(), xyz)) ** 0.5 < tol:
                break

    def move_ee(self, xyz):
        raw = list(xyz)
        if not (WORKSPACE["x"][0] <= raw[0] <= WORKSPACE["x"][1] and
                WORKSPACE["y"][0] <= raw[1] <= WORKSPACE["y"][1] and
                WORKSPACE["z"][0] <= raw[2] <= WORKSPACE["z"][1]):
            self.collision = True
        x = min(max(xyz[0], WORKSPACE["x"][0]), WORKSPACE["x"][1])
        y = min(max(xyz[1], WORKSPACE["y"][0]), WORKSPACE["y"][1])
        z = min(max(xyz[2], WORKSPACE["z"][0]), WORKSPACE["z"][1])
        self._goto_ee_closed_loop([x, y, z])

    def _sync_blocks(self):
        for bid, pid in self._pb_ids.items():
            pos, _ = p.getBasePositionAndOrientation(pid)
            self.blocks[bid]["xyz"] = [pos[0], pos[1], pos[2]]

    def _attach(self, bid, offset=None):
        # both pivots at body origins: block center glued to EE origin.
        # (An earlier version passed world coords as the child pivot, which
        # left the block dragging 15cm behind the gripper and flinging on release.)
        # offset (e.g. slip's tilted carry) is a SMALL child-frame shift, same units as before.
        off = offset or [0, 0, 0]
        self.grasp_cid = p.createConstraint(self.arm, EE_LINK, self._pb_ids[bid], -1,
                                            p.JOINT_FIXED, [0, 0, 0], [0, 0, 0], off)

    def _detach(self):
        if self.grasp_cid is not None:
            p.removeConstraint(self.grasp_cid)
            self.grasp_cid = None

    # ---- SAME GT schema as sim_env.py ------------------------------------
    def get_ground_truth(self):
        self._sync_blocks()
        return {
            "ee_xyz": self.ee_pos(),
            "holding": self.holding,
            "grasp_unstable": self.grasp_unstable,
            "scenario": self.scenario,
            "blocks": {k: {"xyz": list(v["xyz"]), "target_bin": v["target_bin"]}
                       for k, v in self.blocks.items()},
            "bins": {k: {"xyz": list(v["xyz"])} for k, v in self.bins.items()},
            "human_in_zone": False,
        }

    def close(self):
        if self.cid >= 0:
            p.disconnect(self.cid)
            self.cid = -1
