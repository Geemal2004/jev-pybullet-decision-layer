"""Visual demo: PIL schematic of the live Jev decision loop + overlay + GIF capture.
NOTE: schematic top-down view (pybullet has no win32/py3.12 wheel here; the sim
runs headless and every overlay number is a real live Jev answer, not mock).
Usage: python demo.py  (records demo_out/*.gif, prints per-scenario summary)"""
import os
from PIL import Image, ImageDraw, ImageFont

from main import run_episode

OUT = os.path.join(os.path.dirname(__file__), "demo_out")
os.makedirs(OUT, exist_ok=True)

W, H = 1000, 640
FIELD = (0, 0, 640, 640)
PANEL = (640, 0, 1000, 640)
X0, X1, Y0, Y1 = 0.1, 1.0, -0.4, 0.4  # wide enough to show out-of-reach blocks

def _px(x, y):
    fx = (x - X0) / (X1 - X0)
    fy = 1.0 - (y - Y0) / (Y1 - Y0)
    return (int(20 + fx * 600), int(20 + fy * 600))

def _bar(d, x, y, w, label, val, vmax, thr=None, fmt=".2f"):
    d.text((x, y), label, fill=(200, 200, 200))
    d.rectangle([x, y + 14, x + w, y + 26], outline=(90, 90, 90))
    v = max(0.0, min(1.0, (val or 0) / vmax))
    fill = (90, 200, 120) if not (thr is not None and (val or 0) >= thr) else (230, 120, 80)
    d.rectangle([x, y + 14, x + w * v, y + 26], fill=fill)
    if thr is not None:
        tx = x + w * thr / vmax
        d.line([tx, y + 12, tx, y + 28], fill=(230, 120, 80), width=2)
    d.text((x + w + 8, y + 12), format(val or 0, fmt), fill=(240, 240, 240))

def render(payload, trail):
    gt, state, answers, rec = payload["gt"], payload["state"], payload["answers"], payload["rec"]
    img = Image.new("RGB", (W, H), (18, 20, 26))
    d = ImageDraw.Draw(img)
    # field
    d.rectangle([18, 18, 622, 622], outline=(70, 70, 80))
    # reachability boundary x=0.8
    bx, _ = _px(0.8, 0)
    d.line([bx, 20, bx, 620], fill=(120, 90, 40))
    d.text((bx - 108, 24), "reach x=0.8", fill=(150, 120, 70))
    # bins
    for bid, b in gt["bins"].items():
        x, y = _px(b["xyz"][0], b["xyz"][1])
        d.rectangle([x - 34, y - 34, x + 34, y + 34], outline=(190, 170, 120), width=2)
        d.text((x - 24, y - 10), bid, fill=(190, 170, 120))
    # blocks (seen = what Jev judged on; ghost true pos if jittered)
    cols = {"red": (220, 80, 70), "blue": (70, 140, 230)}
    seen = state.get("blocks", {})
    for bid, col in cols.items():
        if bid in seen:
            x, y = _px(seen[bid]["xyz"][0], seen[bid]["xyz"][1])
            r = 13
            d.rectangle([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255))
            d.text((x - 10, y - 28), bid, fill=(240, 240, 240))
            tgt = gt["bins"][gt["blocks"][bid]["target_bin"]]["xyz"]
            tx, ty = _px(tgt[0], tgt[1])
            d.line([x, y, tx, ty], fill=(col[0] // 2, col[1] // 2, col[2] // 2), width=1)
        else:
            d.text((40, 560 + 20 * list(cols).index(bid)), f"block {bid} OCCLUDED", fill=(150, 150, 150))
    # holding tag
    if gt.get("holding"):
        d.text((40, 60), f"holding: {gt['holding']}" + (" UNSTABLE" if gt.get("grasp_unstable") else ""), fill=(255, 220, 120))
    # ee + trail
    for i, ee in enumerate(trail[-12:]):
        ex, ey = ee[0], ee[1]
        x, y = _px(ex, ey)
        rr = 2 + i // 4
        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(90, 220, 130))
    ex, ey = _px(gt["ee_xyz"][0], gt["ee_xyz"][1])
    d.line([ex - 10, ey, ex + 10, ey], fill=(90, 230, 130), width=2)
    d.line([ex, ey - 10, ex, ey + 10], fill=(90, 230, 130), width=2)
    step = payload["step"]
    d.text((40, 40), f"{payload['scenario']}  seed={payload['seed']}  step={step}", fill=(240, 240, 240))
    # panel
    nxt = answers.get("next_skill", {})
    d.text((660, 30), "JEV DECISION (live)", fill=(140, 200, 255))
    d.text((660, 56), f"skill: {nxt.get('choice', '?')}", fill=(255, 255, 255))
    _bar(d, 660, 84, 200, "confidence", nxt.get("confidence"), 1.0)
    _bar(d, 660, 124, 200, "danger (block>=1.5)", (answers.get("risk", {}) or {}).get("score"), 3.0, thr=1.5)
    _bar(d, 660, 164, 200, "feasibility", (answers.get("feasibility", {}) or {}).get("score"), 2.0)
    g = rec["gate"]
    gc = (120, 230, 140) if g["action"] not in ("wait", "abort") else (230, 190, 110)
    d.text((660, 210), f"gate: {g['action']}", fill=gc)
    d.text((660, 230), f"reason: {g['reason'][:38]}", fill=(200, 200, 200))
    d.text((660, 258), f"oracle: {rec['oracle']}  set={rec['oracle_set']}", fill=(200, 200, 200))
    ok = "CORRECT" if rec["correct"] else "MISS"
    d.text((660, 278), ok, fill=(120, 230, 140) if rec["correct"] else (230, 120, 100))
    oc = rec.get("occluded") or []
    if oc:
        d.text((660, 306), f"vision: {', '.join(oc)} OCCLUDED", fill=(230, 190, 110))
    d.text((660, 326), f"outcome: {str(rec['outcome'])[:40]}", fill=(200, 200, 200))
    if rec.get("mock"):
        d.text((660, 354), "MOCK (no key!)", fill=(255, 80, 80))
    logs = payload.get("log", [])
    d.text((660, 390), "trace:", fill=(140, 200, 255))
    for i, ln in enumerate(logs[-8:]):
        d.text((660, 408 + i * 22), ln[:52], fill=(180, 180, 180))
    return img

def record(name, show_breaker_note=False, **kw):
    frames, trail, logs = [], [], []
    def on_step(p):
        trail.append(tuple(p["gt"]["ee_xyz"]))
        r = p["rec"]
        logs.append(f"s{p['step']} {r['pred']}@{r['conf']:.2f} -> {r['gate']['action']} ({r['gate']['reason'][:24]})")
        p["log"] = list(logs)
        frames.append(render(p, trail))
        frames.append(render(p, trail))  # hold each step ~1.8s at 0.9s/frame
    run_episode(verbose=False, on_step=on_step, **kw)
    path = os.path.join(OUT, name + ".gif")
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=900, loop=0)
    n_mock = sum(1 for _ in [])  # counted from runs via rec mock below
    print(f"saved {path} frames={len(frames)}")
    return path

if __name__ == "__main__":
    import json
    from logger import PATH
    scenarios = [
        ("A_clean", dict(seed=1000, scenario="normal")),
        ("B_slip_regrasp", dict(seed=1001, scenario="slip")),
        ("C_cautious_wait", dict(seed=1022, scenario="out_of_reach", occ_prob=0.15)),
        ("D_breaker_after", dict(seed=1006, scenario="out_of_reach", noise_std=0.015, occ_prob=0.15, use_breaker=True)),
        ("D_breaker_before", dict(seed=1006, scenario="out_of_reach", noise_std=0.015, occ_prob=0.15, use_breaker=False)),
    ]
    for name, kw in scenarios:
        if os.path.exists(PATH):
            os.remove(PATH)
        record(name, **kw)
        rows = [json.loads(l) for l in open(PATH)]
        live = sum(1 for r in rows if not r.get("mock"))
        acc = sum(1 for r in rows if r["correct"]) / len(rows)
        print(f" {name}: decisions={len(rows)} live={live} acc={acc:.2f} " +
              " <- MOCK, key missing!" if live < len(rows) else f" {name}: decisions={len(rows)} live acc={acc:.2f}")
