#!/usr/bin/env python3
"""Generate demo.gif from screenshots — 7-step full pipeline demo."""

from PIL import Image, ImageDraw, ImageFont
import os, sys

SCREENS_DIR = os.path.join(os.path.dirname(__file__), "screens")
OUT_PATH = os.path.join(os.path.dirname(__file__), "demo.gif")

# (filename, step_label, annotation, hold_frames)
STEPS = [
    ("01_dashboard.png",         1, "① Dashboard — Your AI content engine",                4),
    ("02_onboard_empty.png",     2, "② Quick Setup — Tell the AI what you care about",    3),
    ("03_user_typing.png",       3, "③ You type your interests",                           3),
    ("04_ai_suggestions.png",    4, "④ AI agent researches & recommends sources",          7),
    ("05_pipeline_running.png",  5, "⑤ AI Agent runs — searches, collects, analyses",     7),
    ("06_report_view.png",       6, "⑥ Bilingual report generated (ZH + EN)",             6),
    ("07b_published_platforms.png", 7, "⑦ Auto-published: WordPress · 飞书 · 微信 · Twitter", 8),
]

TOTAL_STEPS = len(STEPS)
W, H = 1200, 844
BAR_H = 44      # top progress bar
ANN_H = 40      # bottom annotation bar

ACCENT_COLORS = [
    (79, 70, 229),   # indigo
    (16, 185, 129),  # emerald
    (245, 158, 11),  # amber
    (99, 102, 241),  # violet
    (239, 68, 68),   # red
    (14, 165, 233),  # sky
    (168, 85, 247),  # purple
]

def load_font(size):
    for path in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

font_sm = load_font(13)
font_md = load_font(15)
font_bold = load_font(14)

def make_frame(img_path, step_idx, label, annotation):
    step_num = step_idx + 1
    accent = ACCENT_COLORS[step_idx % len(ACCENT_COLORS)]

    base = Image.open(img_path).convert("RGB")
    # Crop / resize to target content area
    content_h = H - BAR_H - ANN_H
    base = base.resize((W, content_h), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H), (13, 17, 23))
    draw = ImageDraw.Draw(canvas)

    # ── Top bar ──────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, BAR_H], fill=(22, 27, 34))
    # Progress track
    track_x, track_w = 120, W - 240
    track_y = BAR_H // 2
    draw.rounded_rectangle([track_x, track_y - 3, track_x + track_w, track_y + 3], radius=3, fill=(48, 54, 61))
    filled_w = int(track_w * step_num / TOTAL_STEPS)
    if filled_w > 6:
        draw.rounded_rectangle([track_x, track_y - 3, track_x + filled_w, track_y + 3], radius=3, fill=accent)

    # Step dots
    for i in range(TOTAL_STEPS):
        dot_x = track_x + int(track_w * (i + 0.5) / TOTAL_STEPS)
        dot_r = 5 if i == step_idx else 3
        col = accent if i <= step_idx else (48, 54, 61)
        draw.ellipse([dot_x - dot_r, track_y - dot_r, dot_x + dot_r, track_y + dot_r], fill=col)

    # Step counter left
    draw.text((8, 13), f"Step {step_num}/{TOTAL_STEPS}", font=font_sm, fill=(148, 163, 184))
    # Label right
    try:
        bbox = draw.textbbox((0, 0), label, font=font_sm)
        lw = bbox[2] - bbox[0]
    except Exception:
        lw = len(label) * 7
    draw.text((W - lw - 8, 15), label, font=font_sm, fill=(*accent, 255))

    # ── Content ──────────────────────────────────────────────────────
    canvas.paste(base, (0, BAR_H))

    # ── Bottom annotation bar ────────────────────────────────────────
    ann_y = BAR_H + content_h
    draw.rectangle([0, ann_y, W, H], fill=(22, 27, 34))
    # Accent left stripe
    draw.rectangle([0, ann_y, 3, H], fill=accent)
    draw.text((14, ann_y + 13), annotation, font=font_md, fill=(226, 232, 240))
    # IntelFlow badge right
    badge = "⚡ IntelFlow"
    try:
        bbox = draw.textbbox((0, 0), badge, font=font_sm)
        bw = bbox[2] - bbox[0]
    except Exception:
        bw = len(badge) * 7
    draw.text((W - bw - 14, ann_y + 14), badge, font=font_sm, fill=(148, 163, 184))

    return canvas


frames = []
durations = []

for idx, (fname, step_num, annotation, hold) in enumerate(STEPS):
    fpath = os.path.join(SCREENS_DIR, fname)
    if not os.path.exists(fpath):
        print(f"  ⚠ Missing: {fpath}")
        continue
    label = f"Step {step_num}/{TOTAL_STEPS}"
    frame = make_frame(fpath, idx, label, annotation)
    frames.append(frame)
    # duration per frame = hold * 600ms (PIL respects duration list per unique frame)
    durations.append(hold * 600)

if not frames:
    print("No frames — aborting.")
    sys.exit(1)

frames[0].save(
    OUT_PATH,
    save_all=True,
    append_images=frames[1:],
    optimize=False,
    loop=0,
    duration=durations,
)
print(f"✓ Saved {len(frames)} frames → {OUT_PATH}")
size_kb = os.path.getsize(OUT_PATH) // 1024
print(f"  Size: {size_kb} KB")
