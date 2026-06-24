"""Emit the compact, budget-bounded artifacts the agent synthesis stage reads.

The agent never reads raw transcripts. It reads ``digest.md`` (a few KB) plus,
if budget allows, a handful of ``shards/`` files describing only the
highest-waste sessions or highest-risk repo areas. The Budget ledger caps the
total emitted size so the synthesis step provably stays under the token ceiling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .budget import Budget
from .savings import projection_lines


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n... [trimmed]\n"


def write_digest(
    out_dir: Path,
    bundle: dict[str, Any],
    token_rep: dict[str, Any] | None,
    repo_rep: dict[str, Any] | None,
    budget: Budget,
) -> None:
    shards_dir = out_dir / "shards"
    shards_dir.mkdir(exist_ok=True)

    lines: list[str] = []
    meta = bundle.get("meta", {})
    lines.append(f"# Agent digest: {meta.get('mode_label','report')}")
    lines.append("")
    lines.append(f"> {meta.get('subtitle','')}")
    lines.append("")
    v = bundle.get("verdict", {})
    lines.append(f"**Verdict:** Grade {v.get('grade','?')}: {v.get('headline','')}")
    lines.append("")
    plines = projection_lines(bundle.get("projection") or {})
    if plines:
        lines.append("## Projected savings (estimate, from usage x benchmark)")
        for pl in plines:
            lines.append(f"- {pl}")
        lines.append("")
    lines.append("## Deterministic KPIs")
    for k in bundle.get("kpis", []):
        lines.append(f"- {k['label']}: {k['value']}")
    lines.append("")
    lines.append("## Deterministic findings (ranked)")
    for i, f in enumerate(bundle.get("findings", []), 1):
        lines.append(f"{i}. [{f.get('severity','').upper()}] {f.get('title','')}")
        lines.append(f"   evidence: {f.get('evidence','')}")
        lines.append(f"   fix: {f.get('recommendation','')}")
    lines.append("")
    lines.append("## Your synthesis task")
    lines.append(_SYNTH_INSTRUCTIONS)

    digest = "\n".join(lines)
    budget.charge_chars(len(digest), "digest.md")
    (out_dir / "digest.md").write_text(digest)

    # Shard the worst sessions / repo locations, bounded by budget allowance.
    allowance = budget.shard_allowance()
    spent = 0
    written = 0
    if token_rep:
        for w in token_rep.get("worst_sessions", []):
            blob = json.dumps({
                "session": w["session_id"],
                "waste_score": w["waste_score"],
                "cache_hit_ratio": w["cache_hit_ratio"],
                "reread_files": w["reread_files"],
                "repeated_cmds": w["repeated_cmds"],
                "big_outputs": w["big_outputs"],
                "tool_histogram": w["tool_histogram"],
            }, indent=2)
            cost = len(blob) // 4
            if spent + cost > allowance:
                break
            (shards_dir / f"session-{written:02d}.json").write_text(_trim(blob, 8000))
            spent += cost
            written += 1
    if repo_rep:
        for f in repo_rep.get("findings", []):
            blob = json.dumps(f, indent=2)
            cost = len(blob) // 4
            if spent + cost > allowance:
                break
            (shards_dir / f"repo-{f['id']}.json").write_text(_trim(blob, 8000))
            spent += cost
    budget.charge(spent, f"{written} session shards + repo shards")


_SYNTH_INSTRUCTIONS = """\
Read this digest and the shards/ files (already budget-bounded). Then append
*tailored* findings the deterministic pass cannot produce, judgment calls only:

1. Map the top waste signals to specific, copy-pasteable edits:
   - CLAUDE.md / AGENTS.md lines to add or cut (quote the exact text).
   - settings.json permission allowlist entries for the recurring safe commands.
   - prompt/structure changes that raise the cacheable-prefix ratio.
2. For repo findings, confirm orphan/dup candidates against dynamic-import risk
   before recommending deletion; mark each autofixable vs needs-review.
3. Rank everything by (impact / effort). Lead with the single highest-leverage move.
4. Write findings back as JSON to synthesis.json using the Finding schema, then
   run `analyze render <out>/bundle.json` after merging. Keep total added context
   under the remaining budget noted in budget.json.
"""
