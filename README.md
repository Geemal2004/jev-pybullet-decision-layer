# Jev Decision Layer for Autonomous Robots — Starting Phase

A pick-and-place decision loop where **Jev** (TypeSafe's System One model) owns fast
structured decisions, a **supervisor** owns safety, and scripted policies own motion.
Built to answer one question before touching real vision or hardware:
*is the decision layer calibrated, attributable, and safe under stress?*

> **Read this first — what the visuals are.**
> The clips in `demo_out/` are **schematic top-down renders of ground-truth state,
> not physics footage**. PyBullet has no prebuilt wheel for this toolchain
> (win32 / Python 3.12) so it could not be installed here; the simulator runs
> headless on deterministic logic and **every overlay number is a real live Jev
> answer**. Nothing in this repo implies contact simulation that never ran.
> (Repeat wherever these GIFs travel: README, slides, shares.)

## The headline result

Across the session, every "gap" that looked like it needed more Jev — more prompts,
a joint skill+target question, a hysteresis band — turned out to be somewhere else
(`policy.py`, oracle scoping, a stagnation loop, a threshold mismatch, an RNG leak,
a logging bug). **Jev itself was never modified.** The discipline that made this
trustworthy wasn't model tuning; it was refusing every degraded number until the
harness was ruled out. That habit is the actual deliverable — it catches the next
bug when real vision or hardware arrives.

Lead artifact: the **D before/after pair** — same seed, breaker off (0.50, stalls)
vs on (0.88, recovers). A visible fix, not a table delta.

## Architecture

```
sim_env.py      PyBullet scene + headless fallback (runs headless here).
                Failure injection: normal / slip / out_of_reach / wrong_bin.
perception.py   Ground-truth -> Jev state (structured JSON + text summary).
                Noise lives HERE only: seeded jitter (noise_std) and occlusion
                (occ_prob) with DECOUPLED rng streams. Oracle/policy see clean GT.
policy.py       Deterministic motion primitives: pick / place / push / regrasp / wait.
                Target selection is deterministic downstream of skill
                (pick -> nearest reachable unplaced; push -> out-of-reach block).
                NOT a Jev question — physical facts already determine it.
decision.py     Single POST to OpenRouter /api/alpha/decisions with ALL questions
                in parallel. Never per control tick; once per decision point.
                Offline mock fallback so sim/eval run without a key.
supervisor.py   Owns safety. Jev output is signal only.
config.py       The 5 Jev questions (noul / choice / score only).
oracle.py       SETS of acceptable actions (multiple valid recoveries/ordering).
logger.py       JSONL per-decision trace.
main.py         Episode loop: perceive -> Jev -> supervise -> act.
eval.py         Set-accuracy + calibration x scenario + danger/feasibility splits.
probe_danger.py Forced place-when-unstable: true positives for the danger detector.
probe_feas.py   Step-0 reachability probes for the feasibility signal.
danger_dist.py  Danger threshold distribution (positives vs clean steps).
diagnose_boundary.py  True-position error histogram (killed the hysteresis idea).
test_independence.py  Standing habit: proves noise streams are independent.
demo.py         Schematic renderer + overlay + GIF recorder (see demo_out/).
```

## The Jev questions (`config.py`)

| Question | Type | Meaning |
|---|---|---|
| `next_skill` | choice | pick / place / push / regrasp / wait + confidence + probabilities |
| `grasp_stable` | noul | P(grasp holds for transport), 0–1 |
| `placed_correctly` | noul | P(block in correct bin), 0–1 |
| `risk` (danger) | score | **Danger only**: collision/drop potential. Ignores reachability. `Low/Moderate/High/Critical` → 0–3 |
| `feasibility` | score | **Geometry only**: can the gripper reach now? `Infeasible/Uncertain/Feasible` → 0–2 |

Danger and feasibility are **separate signals by design**. An out-of-reach block is
not "risky" (no collision/drop potential) — it's a planning/geometry failure.
Conflating them hides gaps; they are evaluated independently.

## Supervisor rules (`supervisor.py`, all evidence-backed)

- `risk >= 1.5` blocks pick/place (probe distribution: positives 1.83–1.91 vs clean
  p90 0.13 → TPR 1.00 / FPR 0.05; 2.0 scored TPR 0.00, rejected).
- Risk blocks **progress actions only** — push/regrasp are mitigations, never blocked
  (blocking regrasp on high risk deadlocked recovery for 8 straight waits).
- Per-skill confidence: pick/place 0.7, regrasp 0.5, push 0.25, wait 0.0.
- Feasibility redirect: pick + last outcome `unreachable` + feas < 1.2 → push.
- Stagnation breaker (`main.py`): 2 zero-progress steps (clean-GT signature,
  noise-proof) → deterministic push of the out-of-reach block.
- Human-in-zone → wait. 3 retries → abort.

## Setup

```powershell
pip install requests          # only runtime dep (Pillow for demo.py)
$env:OPENROUTER_API_KEY = "sk-or-v1-..."   # never commit keys; env only
python main.py                # one episode (mock mode without a key)
python eval.py 15 0.0 0.0     # 60 eps, clean — expect ~0.99, all live
python eval.py 15 0.015 0.0   # jitter-only arm
python eval.py 15 0.0 0.15    # occlusion-only arm
python eval.py 15 0.015 0.15  # combined arm
python probe_danger.py        # danger true positives (forced drops)
python test_independence.py   # noise-stream independence (run after any stochastic change)
python demo.py                # records demo_out/*.gif (live calls)
```

Seeds are fixed (`1000 + episode`), noise is seeded per (seed, step) on decoupled
streams — every batch is exactly reproducible.

## Results (all live Jev, 60 eps / ~315–360 calls per arm, same seeds)

| Arm | set_acc | out_of_reach | Others | Failures |
|---|---|---|---|---|
| Clean | 0.99 | 0.97 | 1.00 | 0 |
| Jitter σ=0.015 | 0.88 | 0.66 | ≥0.99 | 0 |
| Occlusion p=0.15 | 0.99 | 0.97 | 1.00 | 0 |
| Combined | 0.95 | 0.83 | ≥0.99 | 0 |

- Calibration: high bucket ~0.95–1.00; push lives low-conf (~0.3–0.5) and correct —
  underconfident but gated through (push threshold 0.25).
- Danger: slip states ~2.5 pre-rewording; probe pre-drop avg **1.89** (10/10 drops)
  vs clean ~0.15. Threshold **1.5**.
- Feasibility: responsive ex-post (1.69 → 0.80 after a failed pick, redirect built
  on it) but blind ex-ante (step-0 1.75 vs 1.99) — documented limit, not patched over.
- `wait_rate` 0.19–0.28 under noise, all genuine; wrong picks degrade to waits.
  Safe degradation, zero drops, throughout.

## Bug journal (why the numbers can be trusted)

1. **Move-ee clamp bug** — `max(x, *bounds)` collapsed everything to the wall.
   Caught by first offline run.
2. **Scenario-label leakage** — eval tag in Jev state anchored push 8×. Removed;
   model sees physical facts only.
3. **Supervisor deadlocked recovery** — risk ≥ 2.0 gated regrasp. Risk now blocks
   pick/place only.
4. **Skill-without-target** — one `_pick_target` served pick and push; pick executed
   on the unreachable block. Split targets; deterministic downstream of skill.
5. **Threshold mismatch** — reachability defined as 0.35 / 0.4 / 0.85 in three files.
   Unified to workspace physics (0.8 / 0.4).
6. **RNG stream coupling** — toggling occlusion reshuffled jitter draws (0.93 vs 0.86
   for the "same" run). Decoupled `j-`/`o-` streams + `test_independence.py`.
7. **Cumulative counters in logging** — `env.dropped/collision` inflated per-step
   denominators 105 vs true 0. Now keyed on `outcome.reason`.
8. **Hysteresis rejected by data** — all 49 combined errors at `true_red_x = 0.95`
   (0/49 near the 0.8 boundary). Margin band would fix nothing; stagnation breaker
   built instead (verified live: stall → forced push → recovery).

Standing rule earned twice over: **when a second stochastic source is added, prove
independence before trusting the combined number.**

## Demos (`demo_out/` — schematic renders, not physics; see banner)

- **`D_breaker_before.gif` / `D_breaker_after.gif`** — lead with this pair. Same seed
  (1006, combined noise): without the breaker the arm stalls at 0.50; with it,
  `stagnant_2_force_push_red` fires and the task completes at 0.88. The session's
  fix, visible. *(Schematic render of ground-truth state, not physics simulation.)*
- **`B_slip_regrasp.gif`** — the threshold mechanism up close: holding red UNSTABLE,
  danger **1.82** crossing the 1.5 line (orange bar past the marker) → gate regrasp
  @ 1.00 → CORRECT. *(Schematic render, not physics.)*
- **`A_clean.gif`** — baseline correctness, seed 1000, 5/5. *(Schematic render.)*
- **`C_cautious_wait.gif`** — occlusion run (seed 1022): Jev holds instead of acting
  blind;credited as valid caution by the conditional oracle. *(Schematic render.)*

## Roadmap

- Per-block feasibility (global score is ex-ante blind) or hysteresis only if future
  errors actually cluster at a boundary (they didn't this time).
- Real vision noise on top of the now-grounded signals — attribution stays clean
  because the decision layer is bug-checked first.
- Hardware: replace `policy.py` primitives; supervisor thresholds transfer as-is.

## Real-physics backend (answered: decisions transfer, execution doesn't)

`sim_real.py` + `policy_real.py` (KUKA iiwa, rigid bodies, `backend="real"`) keep the
identical GT schema; decision/oracle/scoring untouched. Schematic disclaimer above
still applies to `demo_out/` (recorded on the logic backend).

| Arm (real, 60 eps, live) | set_acc | out_of_reach | Others |
|---|---|---|---|
| Clean | 0.80 | 0.29 | 1.00 |
| Jitter | 0.81 | 0.35 | ≥0.99 |
| Occlusion | 0.83 | 0.37 | 1.00 |
| Combined | 0.84 | 0.47 | ≥0.96 |

vs logic: 0.99 / 0.88 / 0.99 / 0.95. normal/slip/wrong_bin transfer at 1.00 —
the decision layer survives the backend swap. The gap is execution, diagnosed:
real shove displaces ~0.12 vs logic's scripted 0.15, and at 0.95 the block sits
outside the clamp-limited EE envelope entirely (**measured dx=0.000** — the clamp,
not the motors, blocks contact). Chaining pushes is valid (oracle re-derives
`{push}` from current positions every step — verified, no oracle change needed),
but two harness bugs hid it: exact-float stagnation never tripped on micro-jitter
(`STAGNANT=0` all battery; fixed with 1mm quantization) and the wrist collision
mask (added against release-ejection) also neutered push contact (restored
per-skill). Episodes that prove immovable now abort honestly instead of stalling.
Physics bugs fixed along the way: fire-and-forget motion, tool-down IK stall,
world-coords grasp pivot, release catapult. `python eval.py 15 0.0 0.0 real`.
