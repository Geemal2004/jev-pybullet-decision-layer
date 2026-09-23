"""Stitch the live set into one captioned reel. Every card states its provenance:
live clips = real PyBullet contact + live Jev (not schematics)."""
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(__file__), "demo_out")
W, H, FPS = 1328, 640, 2


def card(title, sub, hold=6):
    img = Image.new("RGB", (W, H), (14, 16, 22))
    d = ImageDraw.Draw(img)
    d.text((80, 240), title, fill=(255, 255, 255))
    d.text((80, 280), sub, fill=(160, 200, 255))
    return [np.asarray(img)] * hold


def clip(name):
    return [np.asarray(f) for f in imageio.get_reader(os.path.join(OUT, name))]


reel = []
reel += card("Jev Decision Layer — live on a KUKA iiwa",
             "real PyBullet contact dynamics + live Jev decisions (not schematics)", hold=8)
reel += card("A. Clean baseline — seed 1000", "pick > place x2 > wait. 5/5, all live.")
reel += clip("live_normal_seed1000.mp4")
reel += card("B. Slip recovery — danger 2.1 crosses the 1.5 line",
             "regrasp passes anyway: recovery actions are never risk-blocked.")
reel += clip("live_slip_seed1001.mp4")
reel += card("C1. Breaker OFF — seed 1006, combined noise",
             "8 waits burning to max_steps. Red never touched.")
reel += clip("live_out_of_reach_seed1006_n0.015_o0.15_nobreaker.mp4")
reel += card("C2. Breaker ON — same seed",
             "stagnant_2_force_push_red, then honest immovable abort.")
reel += clip("live_out_of_reach_seed1006_n0.015_o0.15.mp4")
reel += card("Harness did the work; Jev was never retuned.",
             "code + numbers: see README.", hold=8)

out = os.path.join(OUT, "demo_reel.mp4")
imageio.mimsave(out, reel, fps=FPS, quality=8)
print(f"saved {out} frames={len(reel)} (~{len(reel) // FPS}s)")
