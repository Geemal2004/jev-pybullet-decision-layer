"""
build_demo_reel.py

Stitches the four Jev demo clips into one titled, captioned reel.

Usage:
    python build_demo_reel.py

Requires: ffmpeg on PATH, Pillow (pip install pillow)

Expected input files (edit CLIPS below if your paths/names differ):
    live_normal_seed1000.mp4
    live_slip_seed1001.mp4
    live_out_of_reach_seed1006_n0.015_o0.15_nobreaker.mp4
    live_out_of_reach_seed1006_n0.015_o0.15.mp4

Output:
    demo_out/demo_reel_final.mp4
"""

import subprocess
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ---- CONFIG ----------------------------------------------------------

BASE_DIR = Path(r"D:\Projects\jev\robot\demo_out")  # <-- adjust if needed
OUT_DIR = BASE_DIR / "reel_build"
OUT_DIR.mkdir(exist_ok=True)

WIDTH, HEIGHT = 1328, 640     # match your existing clip resolution
FPS = 30
TITLE_CARD_DURATION = 3       # seconds

# drawtext chokes on Windows absolute font paths (drive colon), so use a local
# copy referenced by bare filename, with ffmpeg run from OUT_DIR as CWD.
import shutil
shutil.copy(r"C:\Windows\Fonts\arial.ttf", OUT_DIR / "arial.ttf")
FONTFILE = "arial.ttf"

# Ordered sequence: (clip filename, on-screen caption, title card text or None)
CLIPS = [
    (
        "live_normal_seed1000.mp4",
        "Clean run - live Jev decisions, real KUKA arm physics",
        "Jev as a Decision Layer for Robot Control\nValidated in simulation, tested on real contact dynamics",
    ),
    (
        "live_slip_seed1001.mp4",
        "Block slips mid-grasp - danger score crosses threshold, Jev regrasps",
        "Recovery: Danger Signal Firing Correctly",
    ),
    (
        "live_out_of_reach_seed1006_n0.015_o0.15_nobreaker.mp4",
        "Without stagnation breaker: Jev stalls, waits, never recovers",
        "The Problem: Safe-Stall Under Noise",
    ),
    (
        "live_out_of_reach_seed1006_n0.015_o0.15.mp4",
        "With breaker: forced push, then honest abort at the reach boundary",
        "The Fix: Same Seed, Stagnation Breaker On",
    ),
]

CLOSING_CARD = (
    "Decision layer: 1.00 accuracy on everything physically solvable\n"
    "on both logic and real-physics backends.\n"
    "One characterized limit: a physical reach boundary, not a judgment error.\n\n"
    "github.com/Geemal2004/jev-pybullet-decision-layer"
)

# ---- HELPERS -----------------------------------------------------------

def make_title_card(text: str, out_path: Path, duration: float):
    """Render a text card as a still image, then convert to a short video clip."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 10, 14))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()

    lines = text.split("\n")
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_h = sum(line_heights) + (len(lines) - 1) * 15
    y = (HEIGHT - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (WIDTH - w) // 2
        draw.text((x, y), line, fill=(230, 230, 235), font=font)
        y += h + 15

    png_path = out_path.with_suffix(".png")
    img.save(png_path)

    mp4_path = out_path.with_suffix(".mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(png_path),
        "-t", str(duration),
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={WIDTH}:{HEIGHT}",
        str(mp4_path)
    ], check=True)
    return mp4_path


def caption_clip(src_path: Path, caption: str, out_path: Path):
    """Burn a persistent caption bar onto the bottom of a clip."""
    # Escape characters ffmpeg's drawtext filter treats specially.
    escaped = (
        caption.replace("\\", "\\\\")
               .replace(":", "\\:")
               .replace("'", "\\'")
    )
    drawtext = (
        f"drawtext=fontfile={FONTFILE}:text='{escaped}':"
        f"fontcolor=white:fontsize=22:"
        f"box=1:boxcolor=black@0.55:boxborderw=10:"
        f"x=(w-text_w)/2:y=h-th-25"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(src_path),
        "-vf", drawtext,
        "-c:a", "copy",
        str(out_path)
    ], check=True, cwd=str(OUT_DIR))


def concat_clips(clip_paths, out_path: Path):
    list_file = OUT_DIR / "concat_list.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            # ffmpeg concat demuxer needs forward slashes / escaped paths
            f.write(f"file '{p.as_posix()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(out_path)
    ], check=True)


# ---- MAIN ---------------------------------------------------------------

def main():
    sequence = []

    for i, (filename, caption, title_text) in enumerate(CLIPS):
        src = BASE_DIR / filename
        if not src.exists():
            raise FileNotFoundError(f"Missing clip: {src}")

        if title_text:
            card_path = make_title_card(title_text, OUT_DIR / f"title_{i}", TITLE_CARD_DURATION)
            sequence.append(card_path)

        captioned_path = OUT_DIR / f"captioned_{i}.mp4"
        caption_clip(src, caption, captioned_path)
        sequence.append(captioned_path)

    # closing card
    closing_path = make_title_card(CLOSING_CARD, OUT_DIR / "title_closing", 5)
    sequence.append(closing_path)

    final_out = BASE_DIR / "demo_reel_final.mp4"
    concat_clips(sequence, final_out)

    print(f"\nDone. Final reel: {final_out}")


if __name__ == "__main__":
    main()
