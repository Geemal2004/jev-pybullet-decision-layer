"""
build_demo_reel.py

Stitches the four Jev demo clips into one titled, captioned reel with
scope, results and provenance cards. Every on-screen claim must be backed
by a number in README.md -- update both together.

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
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from config import MODEL
from decision import ENDPOINT

# ---- CONFIG ----------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent
BASE_DIR = REPO_DIR / "demo_out"
OUT_DIR = BASE_DIR / "reel_build"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1328, 640     # match your existing clip resolution
CAMERA_W = 960                # left camera view; Jev panel occupies the rest
FPS = 30
TITLE_CARD_DURATION = 3       # seconds
DENSE_CARD_DURATION = 10      # seconds; text-heavy cards need reading time

# drawtext chokes on Windows absolute font paths (drive colon), so use a local
# copy referenced by bare filename, with ffmpeg run from OUT_DIR as CWD.
import shutil
shutil.copy(r"C:\Windows\Fonts\arial.ttf", OUT_DIR / "arial.ttf")
FONTFILE = "arial.ttf"

# Captions avoid ':' ',' '%' and quotes -- all special to ffmpeg drawtext.
# Ordered sequence: (clip filename, top label, bottom caption, title card or None)
CLIPS = [
    (
        "live_normal_seed1000.mp4",
        "seed 1000 - normal - no noise",
        "Clean run - live Jev skill decisions on a simulated KUKA iiwa - 5/5 correct",
        "Jev as a Decision Layer for Robot Control\n"
        "Simulated KUKA iiwa - PyBullet rigid-body physics\n"
        "Simulation only - no physical hardware",
    ),
    (
        "live_slip_seed1001.mp4",
        "seed 1001 - slip injected - no noise",
        "Block slips mid-grasp - danger ~2.1 crosses the 1.5 gate - supervisor allows regrasp",
        "Recovery: Danger Signal Firing Correctly",
    ),
    (
        "live_out_of_reach_seed1006_n0.015_o0.15_nobreaker.mp4",
        "seed 1006 - out_of_reach - jitter 0.015 + occlusion 0.15 - breaker OFF",
        "Without stagnation breaker - 8 waits until max_steps - red block never touched",
        "The Problem: Safe-Stall Under Noise",
    ),
    (
        "live_out_of_reach_seed1006_n0.015_o0.15.mp4",
        "seed 1006 - same settings - breaker ON",
        "Forced push then honest abort - red at 0.95 m is beyond the arm reach (~0.86-0.90 m)",
        "The Fix: Same Seed, Stagnation Breaker On",
    ),
]

SCOPE_CARD = (
    "What Jev controls - and what it does not\n"
    "\n"
    "Jev answers 5 questions once per decision point:\n"
    "  next skill, grasp stable, placed correctly, danger, feasibility.\n"
    "A rule-based supervisor owns safety and can veto or redirect Jev.\n"
    "Motion is scripted primitives: pick / place / push / regrasp / wait.\n"
    "Jev never commands joints or trajectories.\n"
    "\n"
    "Clips are time-lapse: 1 frame per decision step.\n"
    "Side panel shows the raw live Jev answer for that step."
)

RESULTS_CARD = (
    "Aggregate set accuracy - 60 episodes per arm, live Jev, fixed seeds\n"
    "\n"
    "                      Clean  Jitter  Occl.  Combined\n"
    "Logic backend          0.99   0.88   0.99   0.95\n"
    "Real-physics backend   0.80   0.81   0.83   0.84\n"
    "\n"
    "Real physics, normal / slip / wrong_bin:  1.00 clean, >=0.96 all arms\n"
    "Real physics, out_of_reach:               0.29 - 0.47\n"
    "  red at 0.95 m is beyond the true reach envelope (IK probe)\n"
    "  15/15 of these episodes end in an honest abort, 0 stalls\n"
    "Logic backend: 0 drops, 0 failures in every arm"
)

CLOSING_CARD = (
    "Decisions transfer from logic to real-physics simulation:\n"
    "normal / slip / wrong_bin at 1.00 (clean).\n"
    "The out_of_reach gap is execution, not judgment -\n"
    "a measured reach limit, aborted honestly.\n"
    "Jev was never retuned - every fix was in the harness.\n"
    "Not yet tested: real hardware, real vision.\n"
    "\n"
    "github.com/Geemal2004/jev-pybullet-decision-layer"
)

# ---- HELPERS -----------------------------------------------------------

def git_revision() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_DIR,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=REPO_DIR, capture_output=True, text=True,
                               check=True).stdout.strip()
        return sha + (" (uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def provenance_card() -> str:
    dates = sorted(datetime.fromtimestamp((BASE_DIR / f).stat().st_mtime).date()
                   for f, *_ in CLIPS)
    recorded = str(dates[0]) if dates[0] == dates[-1] else f"{dates[0]} to {dates[-1]}"
    return (
        "Provenance\n"
        "\n"
        f"Code        commit {git_revision()}\n"
        f"Model       {MODEL}\n"
        f"Endpoint    {ENDPOINT}\n"
        "Simulator   PyBullet, KUKA iiwa, rigid bodies (backend=real)\n"
        f"Recorded    {recorded}   reel built {datetime.now().date()}\n"
        "Seeds       1000, 1001, 1006 (fixed; noise seeded per seed+step)\n"
        "Mock calls  any offline fallback is flagged red on the panel\n"
        "\n"
        "Reproduce   python demo_live.py SEED SCENARIO [noise occ on|off]\n"
        "            python eval.py 15 0.0 0.0 real"
    )


def make_title_card(text: str, out_path: Path, duration: float,
                    font_name: str = "arial.ttf", font_size: int = 40,
                    align: str = "center"):
    """Render a text card as a still image, then convert to a short video clip.
    align="block" left-aligns lines inside a centred block (keeps tables aligned
    with a monospace font)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 10, 14))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(font_name, font_size)
    except OSError:
        font = ImageFont.load_default()

    lines = text.split("\n")
    line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
    gap = font_size // 3
    total_h = len(lines) * line_h + (len(lines) - 1) * gap
    y = (HEIGHT - total_h) // 2
    block_w = max(draw.textlength(line, font=font) for line in lines)
    block_x = (WIDTH - block_w) // 2

    for line in lines:
        if align == "block":
            x = block_x
        else:
            x = (WIDTH - draw.textlength(line, font=font)) // 2
        draw.text((x, y), line, fill=(230, 230, 235), font=font)
        y += line_h + gap

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


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
    )


def caption_clip(src_path: Path, label: str, caption: str, out_path: Path):
    """Burn a provenance label (top-left) and a caption bar (bottom) onto a clip."""
    top = (
        f"drawtext=fontfile={FONTFILE}:text='{_escape(label + ' - time-lapse')}':"
        f"fontcolor=white@0.9:fontsize=16:"
        f"box=1:boxcolor=black@0.55:boxborderw=6:"
        f"x=12:y=12"
    )
    bottom = (
        f"drawtext=fontfile={FONTFILE}:text='{_escape(caption)}':"
        f"fontcolor=white:fontsize=22:"
        f"box=1:boxcolor=black@0.55:boxborderw=10:"
        f"x=max(10\\,({CAMERA_W}-text_w)/2):y=h-th-25"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(src_path),
        "-vf", f"{top},{bottom}",
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
    for filename, *_ in CLIPS:
        if not (BASE_DIR / filename).exists():
            raise FileNotFoundError(f"Missing clip: {BASE_DIR / filename}")

    sequence = []

    for i, (filename, label, caption, title_text) in enumerate(CLIPS):
        if title_text:
            card_path = make_title_card(title_text, OUT_DIR / f"title_{i}", TITLE_CARD_DURATION)
            sequence.append(card_path)

        if i == 0:
            sequence.append(make_title_card(SCOPE_CARD, OUT_DIR / "title_scope",
                                            DENSE_CARD_DURATION, font_size=30,
                                            align="block"))

        captioned_path = OUT_DIR / f"captioned_{i}.mp4"
        caption_clip(BASE_DIR / filename, label, caption, captioned_path)
        sequence.append(captioned_path)

    sequence.append(make_title_card(RESULTS_CARD, OUT_DIR / "title_results",
                                    DENSE_CARD_DURATION, font_name="consola.ttf",
                                    font_size=26, align="block"))
    sequence.append(make_title_card(CLOSING_CARD, OUT_DIR / "title_closing",
                                    7, font_size=34))
    sequence.append(make_title_card(provenance_card(), OUT_DIR / "title_provenance",
                                    DENSE_CARD_DURATION, font_name="consola.ttf",
                                    font_size=24, align="block"))

    final_out = BASE_DIR / "demo_reel_final.mp4"
    concat_clips(sequence, final_out)

    print(f"\nDone. Final reel: {final_out}")


if __name__ == "__main__":
    main()
