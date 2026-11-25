"""Subtitle and end-card images rendered with Pillow.

Many FFmpeg builds (including Homebrew's) ship without libass/freetype, so the `subtitles`
and `drawtext` filters are not portable. Rendering PNGs here and overlaying them works with
any FFmpeg, and the bundled Noto fonts render Ethiopic script on every machine.
"""

from __future__ import annotations

import contextlib
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.common import FONTS

LATIN_FONT = FONTS / "NotoSans.ttf"
ETHIOPIC_FONT = FONTS / "NotoSansEthiopic.ttf"
ETHIOPIC_RE = re.compile(r"[ሀ-᎟ⶀ-⷟꬀-꬯]")

SUB_FILL = (255, 255, 255, 255)
SUB_STROKE = (0, 0, 0, 255)
SUB_BOX = (0, 0, 0, 110)
CARD_BG = (18, 16, 14)
CARD_FG = (238, 230, 214)
CARD_DIM = (170, 160, 145)


@lru_cache(maxsize=32)
def font(size: int, ethiopic: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = ETHIOPIC_FONT if ethiopic else LATIN_FONT
    if not path.exists():
        return ImageFont.load_default(size)
    f = ImageFont.truetype(str(path), size)
    # variable fonts expose named instances; static fonts raise, and we keep the default
    with contextlib.suppress(OSError, ValueError):
        f.set_variation_by_name("Bold" if bold else "Regular")
    return f


def font_for(text: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return font(size, ethiopic=bool(ETHIOPIC_RE.search(text)), bold=bold)


def subtitle_style(width: int, height: int) -> tuple[int, int]:
    """(font size, bottom margin) scaled to the frame; vertical keeps clear of platform UI."""
    vertical = height > width
    size = round(width * (0.052 if vertical else 0.034))
    margin = round(height * (0.22 if vertical else 0.08))
    return size, margin


def render_subtitle(text: str, width: int, height: int, out: Path) -> tuple[Path, int, int]:
    """Render the cue as a tight transparent PNG; return (path, x, y) to place it in the frame.

    Centred horizontally, bottom-anchored inside the safe area. A tight image (not full-frame)
    keeps the per-frame overlay cost small.
    """
    size, margin = subtitle_style(width, height)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = text.split("\n")
    f = font_for(text, size)
    stroke = max(2, size // 14)
    line_h = round(size * 1.28)
    pad = round(size * 0.45)
    widths = [probe.textlength(line, font=f) for line in lines]
    box_w = min(int(max(widths)) + 2 * pad, width)
    box_h = line_h * len(lines) + pad
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, box_w - 1, box_h - 1), radius=size // 3, fill=SUB_BOX)
    y = pad * 0.4
    for line, w in zip(lines, widths, strict=True):
        draw.text(((box_w - w) / 2, y), line, font=f, fill=SUB_FILL,
                  stroke_width=stroke, stroke_fill=SUB_STROKE)
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    x = (width - box_w) // 2
    top = height - margin - box_h
    return out, x - x % 2, top - top % 2


def render_end_card(lines: list[str], width: int, height: int, out: Path) -> Path:
    """Opaque end card. First line large (title), the rest smaller (AI disclosure, credits)."""
    img = Image.new("RGB", (width, height), CARD_BG)
    draw = ImageDraw.Draw(img)
    base = min(width, height)
    sizes = [round(base * 0.075)] + [round(base * 0.036)] * (len(lines) - 1)
    gaps = [round(base * 0.06)] + [round(base * 0.022)] * (len(lines) - 1)
    max_w = width * 0.86
    rendered = []
    for i, (line, size) in enumerate(zip(lines, sizes, strict=True)):
        f = font_for(line, size, bold=i == 0)
        while draw.textlength(line, font=f) > max_w and size > 12:
            size -= 2
            f = font_for(line, size, bold=i == 0)
        rendered.append((line, f, size))
    total_h = sum(s for _, _, s in rendered) + sum(gaps[1:])
    y = (height - total_h) / 2
    for i, (line, f, size) in enumerate(rendered):
        w = draw.textlength(line, font=f)
        draw.text(((width - w) / 2, y), line, font=f, fill=CARD_FG if i < 2 else CARD_DIM)
        y += size + (gaps[i + 1] if i + 1 < len(gaps) else 0)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
