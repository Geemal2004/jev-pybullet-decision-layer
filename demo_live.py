"""Live GUI demo: real arm + on-screen Jev overlay + mp4 capture.
Usage: python demo_live.py [seed] [scenario]   (default: 1000 normal)
Needs a display (p.GUI) and an OPENROUTER_API_KEY for live answers."""
import os
import sys
import time

import pybullet as p
from PIL import Image, ImageDraw

from main import run_episode
from debug_panel import DebugPanel

OUT = os.path.join(os.path.dirname(__file__), "demo_out")
os.makedirs(OUT, exist_ok=True)

PANEL_W = 360


def draw_panel(base, rec, answers):
    """PIL side panel: same six lines as the 3D overlay, guaranteed legible."""
    img = Image.new("RGB", (PANEL_W, 640), (18, 20, 26))
    d = ImageDraw.Draw(img)
    nxt = answers.get("next_skill", {})
    risk = (answers.get("risk", {}) or {}).get("score", 0) or 0
    feas = (answers.get("feasibility", {}) or {}).get("score", 0) or 0
    gate = rec["gate"]

    def bar(y, label, val, vmax, thr=None):
        d.text((16, y), label, fill=(200, 200, 200))
        d.rectangle([16, y + 14, 16 + 260, y + 26], outline=(90, 90, 90))
        v = max(0.0, min(1.0, val / vmax))
        fill = (90, 200, 120) if not (thr is not None and val >= thr) else (230, 120, 80)
        d.rectangle([16, y + 14, 16 + 260 * v, y + 26], fill=fill)
        if thr is not None:
            tx = 16 + 260 * thr / vmax
            d.line([tx, y + 12, tx, y + 28], fill=(230, 120, 80), width=2)
        d.text((282, y + 12), f"{val:.2f}", fill=(240, 240, 240))

    d.text((16, 14), "JEV DECISION (live)", fill=(140, 200, 255))
    d.text((16, 36), f"skill: {nxt.get('choice', '?')}", fill=(255, 255, 255))
    bar(62, "confidence", nxt.get("confidence") or 0, 1.0)
    bar(102, "danger (block>=1.5)", risk, 3.0, thr=1.5)
    bar(142, "feasibility", feas, 2.0)
    gc = (120, 230, 140) if gate["action"] not in ("wait", "abort") else (230, 190, 110)
    d.text((16, 188), f"gate: {gate['action']}", fill=gc)
    d.text((16, 208), f"reason: {gate['reason'][:36]}", fill=(200, 200, 200))
    d.text((16, 234), f"oracle: {rec['oracle']} set={rec['oracle_set']}", fill=(200, 200, 200))
    ok = rec["correct"]
    d.text((16, 254), "CORRECT" if ok else "MISS",
           fill=(120, 230, 140) if ok else (230, 120, 100))
    d.text((16, 282), f"outcome: {str(rec['outcome'])[:38]}", fill=(200, 200, 200))
    if rec.get("mock"):
        d.text((16, 310), "MOCK (no key!)", fill=(255, 80, 80))
    base.paste(img, (960, 0))
    return base


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    scenario = sys.argv[2] if len(sys.argv) > 2 else "normal"
    panel = DebugPanel()
    frames = []
    # NOTE: pybullet's mp4 logging shells out to ffmpeg (absent here), so capture
    # getCameraImage frames (GUI view incl. debug text) and save a GIF via Pillow.
    gif = os.path.join(OUT, f"live_{scenario}_seed{seed}.gif")

    def on_step(payload):
        panel.update(payload["rec"], payload["answers"])  # 3D text (visible in window)
        w, h, rgb, _, _ = p.getCameraImage(960, 640,
                                           renderer=p.ER_BULLET_HARDWARE_OPENGL)
        import numpy as _np
        frame = Image.new("RGB", (960 + PANEL_W, 640), (18, 20, 26))
        frame.paste(Image.fromarray(
            _np.array(rgb, dtype="uint8").reshape((h, w, 4))[..., :3]), (0, 0))
        frames.append(draw_panel(frame, payload["rec"], payload["answers"]))
        time.sleep(1.5)  # throttle: tight step loop is unwatchable otherwise

    run_episode(seed=seed, scenario=scenario, verbose=True, backend="real",
                gui=True, on_step=on_step)
    frames[0].save(gif, save_all=True, append_images=frames[1:],
                   duration=1500, loop=0)
    print(f"saved {gif} frames={len(frames)}")


if __name__ == "__main__":
    main()
