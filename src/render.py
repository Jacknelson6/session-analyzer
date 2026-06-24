"""Render a report bundle into a polished terminal view or Markdown.

Two surfaces from one data model:
  - ``render_terminal`` : boxed, colored, scannable TUI for Claude Code / shells.
  - ``render_markdown``  : clean Markdown for GUI clients and PRs.

The design language: one accent color, semantic severity hues, generous
whitespace, right-aligned numbers, and a single "verdict" line up top so a
reader gets the headline before any detail.
"""

from __future__ import annotations

from typing import Any

from .savings import projection_lines
from .theme import BOX, GLYPH, PALETTE, Style, hbar, make_style, pad, sparkline

WIDTH = 76


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _rule(st: Style, width: int = WIDTH, role: str = "faint") -> str:
    return st.rgb(BOX["h"] * width, PALETTE[role])


def _box_top(st: Style, width: int = WIDTH) -> str:
    return st.rgb(BOX["tl"] + BOX["h"] * (width - 2) + BOX["tr"], PALETTE["faint"])


def _box_bottom(st: Style, width: int = WIDTH) -> str:
    return st.rgb(BOX["bl"] + BOX["h"] * (width - 2) + BOX["br"], PALETTE["faint"])


def _box_line(st: Style, inner: str, width: int = WIDTH) -> str:
    v = st.rgb(BOX["v"], PALETTE["faint"])
    return v + " " + pad(inner, width - 4) + " " + v


def banner(st: Style, title: str, subtitle: str) -> list[str]:
    lines = [_box_top(st)]
    lines.append(_box_line(st, st.role(title, "accent", bold=True)))
    lines.append(_box_line(st, st.dim(subtitle)))
    lines.append(_box_bottom(st))
    return lines


def verdict_line(st: Style, grade: str, headline: str) -> str:
    color = {"A": "good", "B": "low", "C": "medium", "D": "high", "F": "high"}.get(
        grade[0] if grade else "", "info")
    badge = st.role(f" {grade} ", color, bold=True)
    return f"{badge}  {st.bold(headline)}"


def severity_chip(st: Style, sev: str) -> str:
    return st.role(GLYPH.get(sev, GLYPH["info"]) + " " + sev.upper(), sev, bold=True)


def kpi_row(st: Style, label: str, value: str, role: str = "text") -> str:
    return "  " + pad(st.dim(label), 30) + st.role(value, role, bold=True)


def render_finding(st: Style, f: dict[str, Any], idx: int) -> list[str]:
    lines: list[str] = []
    chip = severity_chip(st, f.get("severity", "info"))
    title = st.bold(f.get("title", ""))
    impact = f.get("impact_usd", 0) or 0
    head = f"{st.dim(f'{idx:>2}.')} {chip}  {title}"
    lines.append(head)
    if impact > 0:
        lines.append("     " + st.role(f"~{_money(impact)} reclaimable", "good"))
    ev = f.get("evidence", "")
    if ev:
        lines.append("     " + st.dim(_wrap(ev, WIDTH - 6, "     ")))
    rec = f.get("recommendation", "")
    if rec:
        lines.append("     " + st.role(GLYPH["arrow"] + " ", "accent") + _wrap(rec, WIDTH - 8, "       "))
    locs = f.get("locations") or []
    if locs:
        shown = ", ".join(locs[:4]) + ("" if len(locs) <= 4 else f" (+{len(locs)-4})")
        lines.append("     " + st.dim("at " + shown))
    lines.append("")
    return lines


def _wrap(text: str, width: int, indent: str) -> str:
    words = text.split()
    out, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return ("\n" + indent).join(out)


def render_terminal(bundle: dict[str, Any], style: Style | None = None) -> str:
    st = style or make_style()
    out: list[str] = []
    meta = bundle.get("meta", {})
    out += banner(
        st,
        "  session-analyzer  ·  " + meta.get("mode_label", "report"),
        meta.get("subtitle", ""),
    )
    out.append("")

    if bundle.get("empty"):
        out.append("  " + st.role("○ ", "info") + st.bold(bundle.get("verdict", {}).get("headline", "Nothing to analyze")))
        out.append("")
        if bundle.get("footer"):
            out.append("  " + st.dim(_wrap(bundle["footer"], WIDTH - 4, "  ")))
        return "\n".join(out)

    v = bundle.get("verdict", {})
    if v:
        out.append(verdict_line(st, v.get("grade", "C"), v.get("headline", "")))
        out.append("")

    # Projected savings (the "what would I save?" headline)
    plines = projection_lines(bundle.get("projection") or {})
    if plines:
        out.append("  " + st.role(GLYPH.get("arrow", "->") + " Projected savings", "good", bold=True))
        out.append("     " + st.bold(plines[0]))
        for extra in plines[1:]:
            out.append("     " + st.dim(extra))
        out.append("     " + st.dim("estimate, from your usage x our benchmark"))
        out.append("")

    # KPI strip
    for kpi in bundle.get("kpis", []):
        out.append(kpi_row(st, kpi["label"], kpi["value"], kpi.get("role", "text")))
    if bundle.get("kpis"):
        out.append("")

    # Optional chronological trend sparkline
    trend = bundle.get("trend")
    if trend and trend.get("values"):
        spark = sparkline(trend["values"], st, "accent")
        out.append("  " + pad(st.dim(trend["label"]), 30) + spark + "  " + st.dim(trend.get("note", "")))
        out.append("")

    # Optional bar chart section (e.g., cost by repo or worst sessions)
    for chart in bundle.get("charts", []):
        out.append("  " + st.role(chart["title"], "accent", bold=True))
        rows = chart["rows"]
        maxv = max((r["value"] for r in rows), default=0) or 1
        labelw = min(28, max((len(r["label"]) for r in rows), default=0))
        for r in rows:
            bar = hbar(r["value"], maxv, 24, st, r.get("role", "bar"))
            out.append(
                "    " + pad(r["label"][:labelw], labelw) + "  " + bar + "  "
                + st.dim(r.get("note", ""))
            )
        out.append("")

    # Findings
    findings = bundle.get("findings", [])
    if findings:
        out.append("  " + st.role(f"Findings ({len(findings)})", "accent", bold=True))
        out.append("")
        for i, f in enumerate(findings, 1):
            out += render_finding(st, f, i)

    # Footer / next actions
    footer = bundle.get("footer")
    if footer:
        out.append(_rule(st))
        out.append("  " + st.dim(footer))
    return "\n".join(out)


def render_markdown(bundle: dict[str, Any]) -> str:
    meta = bundle.get("meta", {})
    out = [f"# {meta.get('mode_label', 'Report')}", ""]
    if meta.get("subtitle"):
        out.append(f"_{meta['subtitle']}_\n")
    v = bundle.get("verdict", {})
    if v:
        out.append(f"**Grade {v.get('grade','C')}**: {v.get('headline','')}\n")
    plines = projection_lines(bundle.get("projection") or {})
    if plines:
        out.append("## Projected savings")
        out.append(f"**{plines[0]}**  ")
        for extra in plines[1:]:
            out.append(f"{extra}  ")
        out.append("\n_Estimate, from your usage × our benchmark._\n")
    kpis = bundle.get("kpis", [])
    if kpis:
        out.append("| Metric | Value |")
        out.append("| --- | --- |")
        for k in kpis:
            out.append(f"| {k['label']} | {k['value']} |")
        out.append("")
    trend = bundle.get("trend")
    if trend and trend.get("values"):
        spark = sparkline(trend["values"], make_style(force=False))
        out.append(f"**{trend['label']}:** `{spark}` {trend.get('note','')}\n")
    for chart in bundle.get("charts", []):
        out.append(f"### {chart['title']}\n")
        maxv = max((r["value"] for r in chart["rows"]), default=0) or 1
        out.append("| Item | | Value |")
        out.append("| --- | :-- | ---: |")
        for r in chart["rows"]:
            blocks = int(round(r["value"] / maxv * 12))
            bar = "█" * blocks + "·" * (12 - blocks)
            out.append(f"| {r['label']} | `{bar}` | {r.get('note','')} |")
        out.append("")
    findings = bundle.get("findings", [])
    if findings:
        out.append(f"## Findings ({len(findings)})\n")
        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "info").upper()
            out.append(f"### {i}. [{sev}] {f.get('title','')}")
            if f.get("impact_usd"):
                out.append(f"- **Impact:** ~${f['impact_usd']:,.2f} reclaimable")
            if f.get("evidence"):
                out.append(f"- **Evidence:** {f['evidence']}")
            if f.get("recommendation"):
                out.append(f"- **Fix:** {f['recommendation']}")
            if f.get("locations"):
                out.append(f"- **At:** {', '.join(f['locations'][:8])}")
            out.append("")
    if bundle.get("footer"):
        out.append("---\n")
        out.append(bundle["footer"])
    return "\n".join(out)
