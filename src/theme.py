"""Terminal styling primitives: palette, glyphs, boxes, bars, sparklines.

Goal: a report that looks composed and calm in any TUI, and degrades cleanly
when color is unavailable. We honor the ``NO_COLOR`` convention and auto-disable
styling when stdout is not a TTY, so piping to a file yields clean text.

No third-party deps; truecolor escapes only, with a graceful monochrome path.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# A restrained, high-contrast palette tuned for dark terminals. Values are
# (r, g, b). One accent, semantic severity hues, and muted structure tones, so
# the eye lands on what matters instead of a rainbow.
PALETTE = {
    "accent": (122, 162, 247),   # periwinkle, the single brand accent
    "accent_dim": (86, 95, 137),
    "high": (247, 118, 142),     # rose, critical
    "medium": (224, 175, 104),   # amber, warning
    "low": (158, 206, 106),      # green, minor
    "info": (125, 207, 255),     # cyan, informational
    "good": (158, 206, 106),
    "text": (192, 202, 245),
    "muted": (109, 120, 162),
    "faint": (65, 72, 104),
    "bar": (122, 162, 247),
    "bar_track": (52, 58, 84),
}

GLYPH = {
    "high": "●",
    "medium": "◆",
    "low": "▪",
    "info": "·",
    "ok": "✓",
    "arrow": "→",
    "bullet": "•",
    "money": "$",
    "spark": "▁▂▃▄▅▆▇█",
    "vbar": " ▏▎▍▌▋▊▉█",
}

# Rounded box-drawing set.
BOX = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
    "h": "─", "v": "│", "ml": "├", "mr": "┤",
}


@dataclass
class Style:
    enabled: bool

    def rgb(self, text: str, color: tuple[int, int, int], *, bold: bool = False, dim: bool = False) -> str:
        if not self.enabled:
            return text
        r, g, b = color
        pre = "\x1b[38;2;%d;%d;%dm" % (r, g, b)
        if bold:
            pre = "\x1b[1m" + pre
        if dim:
            pre = "\x1b[2m" + pre
        return pre + text + "\x1b[0m"

    def role(self, text: str, role: str, **kw) -> str:
        return self.rgb(text, PALETTE.get(role, PALETTE["text"]), **kw)

    def bold(self, text: str) -> str:
        return "\x1b[1m" + text + "\x1b[0m" if self.enabled else text

    def dim(self, text: str) -> str:
        return self.rgb(text, PALETTE["muted"])


def make_style(force: bool | None = None) -> Style:
    if force is not None:
        return Style(enabled=force)
    if os.environ.get("NO_COLOR") is not None:
        return Style(enabled=False)
    if os.environ.get("SA_FORCE_COLOR") is not None:
        return Style(enabled=True)
    return Style(enabled=sys.stdout.isatty())


def visible_len(s: str) -> int:
    """Length of a string ignoring ANSI escape sequences."""
    out, i, n = 0, 0, len(s)
    while i < n:
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j == -1:
                break
            i = j + 1
            continue
        out += 1
        i += 1
    return out


def pad(s: str, width: int, align: str = "left") -> str:
    gap = max(0, width - visible_len(s))
    if align == "right":
        return " " * gap + s
    if align == "center":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


def hbar(value: float, maximum: float, width: int, st: Style, role: str = "bar") -> str:
    """A fractional horizontal bar using eighth-block glyphs."""
    if maximum <= 0:
        frac = 0.0
    else:
        frac = max(0.0, min(1.0, value / maximum))
    full = frac * width
    whole = int(full)
    rem = full - whole
    blocks = GLYPH["vbar"]
    bar = "█" * whole
    if whole < width:
        idx = int(rem * (len(blocks) - 1))
        bar += blocks[idx]
        bar += " " * (width - whole - 1)
    filled = st.role(bar.rstrip(" ") or "", role)
    track_len = width - visible_len(bar.rstrip(" "))
    track = st.rgb("─" * max(0, track_len), PALETTE["bar_track"])
    return filled + track


def sparkline(values: list[float], st: Style, role: str = "accent") -> str:
    if not values:
        return ""
    chars = GLYPH["spark"]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    out = "".join(chars[min(len(chars) - 1, int((v - lo) / span * (len(chars) - 1)))] for v in values)
    return st.role(out, role)
