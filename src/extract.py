"""Deterministic session metrics + token-efficiency findings.

This is the zero-LLM heavy lifter for the "save tokens" intent. It crunches
arbitrarily large transcript volumes into a compact, bounded metrics object and
a ranked list of concrete, evidence-backed findings. An agent reads the summary,
not the megabytes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from .findings import Finding
from .pricing import DEFAULT_PRICE, Price, cache_miss_cost_usd, cost_usd
from .sessions import Session

# Heuristic thresholds. Centralized so optimization rounds can tune them in one
# place and the README can document them honestly.
THRESHOLDS = {
    "low_cache_ratio": 0.55,        # below this, prefix-caching is being wasted
    "reread_count": 3,              # same file Read >= N times in a session
    "big_output_chars": 60_000,     # a single tool result this large floods context
    "retry_identical_cmds": 2,      # same Bash command run >= N times
    "high_denial_ratio": 0.04,      # tool errors / tool calls
    "compaction_warn": 2,           # compaction events per session
}

CHARS_PER_TOKEN = 4  # rough industry constant for English+code


def _tok(chars: int) -> int:
    return max(0, round(chars / CHARS_PER_TOKEN))


def _sess(n: int) -> str:
    return f"{n} session" if n == 1 else f"{n} sessions"


@dataclass
class SessionMetric:
    session_id: str
    repo: str | None
    branch: str | None
    started: str | None
    ended: str | None
    turns: int
    assistant_turns: int
    size_bytes: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cache_hit_ratio: float
    est_cost_usd: float
    cache_waste_usd: float
    tool_calls: int
    tool_errors: int
    denial_ratio: float
    compactions: int
    reread_files: dict[str, int] = field(default_factory=dict)
    repeated_cmds: dict[str, int] = field(default_factory=dict)
    big_outputs: int = 0
    tool_histogram: dict[str, int] = field(default_factory=dict)
    waste_score: float = 0.0  # 0..100, higher = more reclaimable waste


def _norm_cmd(cmd: str) -> str:
    return " ".join((cmd or "").split())[:160]


def analyze_session(session: Session, price: Price = DEFAULT_PRICE) -> SessionMetric:
    inp = sum(t.input_tokens for t in session.turns)
    out = sum(t.output_tokens for t in session.turns)
    cread = sum(t.cache_read_tokens for t in session.turns)
    cwrite = sum(t.cache_creation_tokens for t in session.turns)
    total_ctx = inp + cread + cwrite
    cache_ratio = (cread / total_ctx) if total_ctx else 0.0

    tool_calls = 0
    tool_errors = 0
    compactions = 0
    reads: Counter = Counter()
    cmds: Counter = Counter()
    big_outputs = 0
    histogram: Counter = Counter()

    for t in session.turns:
        if t.is_compaction:
            compactions += 1
        tool_errors += t.tool_errors
        for name, inp_obj in zip(t.tool_calls, t.tool_inputs):
            tool_calls += 1
            histogram[name] += 1
            if name == "Read":
                fp = inp_obj.get("file_path")
                if fp:
                    reads[fp] += 1
            elif name == "Bash":
                c = inp_obj.get("command")
                if c:
                    cmds[_norm_cmd(c)] += 1
        for rc in t.tool_result_chars:
            if rc >= THRESHOLDS["big_output_chars"]:
                big_outputs += 1

    denial_ratio = (tool_errors / tool_calls) if tool_calls else 0.0
    reread = {f: n for f, n in reads.items() if n >= THRESHOLDS["reread_count"]}
    repeated = {c: n for c, n in cmds.items() if n >= THRESHOLDS["retry_identical_cmds"]}
    est_cost = cost_usd(inp, out, cread, cwrite, price)
    cache_waste = cache_miss_cost_usd(inp, price) if cache_ratio < THRESHOLDS["low_cache_ratio"] else 0.0

    metric = SessionMetric(
        session_id=session.session_id,
        repo=session.cwd,
        branch=session.git_branch,
        started=session.started,
        ended=session.ended,
        turns=len(session.turns),
        assistant_turns=len(session.assistant_turns),
        size_bytes=session.size_bytes,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cread,
        cache_creation_tokens=cwrite,
        cache_hit_ratio=round(cache_ratio, 4),
        est_cost_usd=round(est_cost, 4),
        cache_waste_usd=round(cache_waste, 4),
        tool_calls=tool_calls,
        tool_errors=tool_errors,
        denial_ratio=round(denial_ratio, 4),
        compactions=compactions,
        reread_files=dict(sorted(reread.items(), key=lambda kv: -kv[1])),
        repeated_cmds=dict(sorted(repeated.items(), key=lambda kv: -kv[1])),
        big_outputs=big_outputs,
        tool_histogram=dict(histogram.most_common()),
    )
    metric.waste_score = _waste_score(metric)
    return metric


def _waste_score(m: SessionMetric) -> float:
    """A 0..100 blend of independent waste signals, weighted by reclaimability."""
    score = 0.0
    # Cache misses are the single biggest, most reliably reclaimable lever.
    if m.cache_hit_ratio < THRESHOLDS["low_cache_ratio"]:
        score += 34 * (1 - m.cache_hit_ratio / THRESHOLDS["low_cache_ratio"])
    score += min(20, 6 * sum(max(0, n - 1) for n in m.reread_files.values()))
    score += min(16, 8 * m.big_outputs)
    score += min(14, 7 * sum(max(0, n - 1) for n in m.repeated_cmds.values()))
    if m.denial_ratio > THRESHOLDS["high_denial_ratio"]:
        score += min(10, 200 * m.denial_ratio)
    score += min(6, 3 * max(0, m.compactions - 1))
    return round(min(100.0, score), 1)


@dataclass
class TokenReport:
    sessions_analyzed: int
    repos: list[str]
    totals: dict[str, Any]
    findings: list[dict[str, Any]]
    worst_sessions: list[dict[str, Any]]
    per_session: list[dict[str, Any]]


def build_token_report(
    sessions: list[Session],
    price: Price = DEFAULT_PRICE,
    top_n: int = 10,
) -> TokenReport:
    metrics = [analyze_session(s, price) for s in sessions]
    metrics = [m for m in metrics if m.turns > 0]

    total_in = sum(m.input_tokens for m in metrics)
    total_out = sum(m.output_tokens for m in metrics)
    total_cread = sum(m.cache_read_tokens for m in metrics)
    total_cwrite = sum(m.cache_creation_tokens for m in metrics)
    total_ctx = total_in + total_cread + total_cwrite
    overall_cache = (total_cread / total_ctx) if total_ctx else 0.0
    total_cost = sum(m.est_cost_usd for m in metrics)
    total_cache_waste = sum(m.cache_waste_usd for m in metrics)

    findings = _token_findings(metrics, overall_cache, total_cache_waste, price)

    repos = sorted({m.repo for m in metrics if m.repo})
    worst = sorted(metrics, key=lambda m: -m.waste_score)[:top_n]

    totals = {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cache_read_tokens": total_cread,
        "cache_creation_tokens": total_cwrite,
        "overall_cache_hit_ratio": round(overall_cache, 4),
        "est_total_cost_usd": round(total_cost, 2),
        "reclaimable_cache_usd": round(total_cache_waste, 2),
        "sessions": len(metrics),
    }
    return TokenReport(
        sessions_analyzed=len(metrics),
        repos=repos,
        totals=totals,
        findings=[asdict(f) for f in findings],
        worst_sessions=[asdict(m) for m in worst],
        per_session=[asdict(m) for m in metrics],
    )


def _token_findings(
    metrics: list[SessionMetric],
    overall_cache: float,
    total_cache_waste: float,
    price: Price,
) -> list[Finding]:
    out: list[Finding] = []

    # Fire when EITHER the blend is poor OR a meaningful dollar amount is
    # reclaimable, so a few cache-wasting sessions cannot hide behind healthy
    # ones that pull the average up.
    low_cache_sessions = [m for m in metrics if m.cache_waste_usd > 0]
    material_waste = total_cache_waste >= 0.50
    systemic = overall_cache < THRESHOLDS["low_cache_ratio"]
    if (systemic or material_waste) and total_cache_waste > 0:
        worst = sorted(low_cache_sessions, key=lambda m: -m.cache_waste_usd)[:3]
        worst_note = ", ".join(f"{m.session_id[:8]} ({m.cache_hit_ratio*100:.0f}%)" for m in worst)
        if systemic:
            # Caching is broadly wasted: a real, high-leverage problem.
            out.append(
                Finding(
                    id="cache-hit-ratio",
                    title="Prompt cache is underused",
                    severity="high" if total_cache_waste >= 1.0 else "medium",
                    category="tokens",
                    evidence=(
                        f"Overall cache-hit ratio is {overall_cache*100:.0f}% (target >= "
                        f"{THRESHOLDS['low_cache_ratio']*100:.0f}%); {len(low_cache_sessions)} of "
                        f"{len(metrics)} sessions cache poorly. Worst: {worst_note}."
                    ),
                    impact_usd=round(total_cache_waste, 2),
                    recommendation=(
                        "Keep a stable, cacheable prefix: pin tool/system/instruction "
                        "content at the top and stop injecting volatile context (timestamps, "
                        "fresh file dumps) mid-prompt. Batch reads so the cached prefix is "
                        "reused across turns."
                    ),
                )
            )
        else:
            # Overall caching is healthy; waste is isolated to a few outliers. Do
            # NOT call this "underused" or rank it high: that contradicts a healthy
            # headline grade and buries the findings that actually matter.
            out.append(
                Finding(
                    id="cache-hit-ratio",
                    title="Cache misses concentrated in a few sessions",
                    severity="low",
                    category="tokens",
                    evidence=(
                        f"Overall cache-hit ratio is healthy at {overall_cache*100:.0f}% "
                        f"(target >= {THRESHOLDS['low_cache_ratio']*100:.0f}%). Only "
                        f"{len(low_cache_sessions)} of {len(metrics)} sessions cache poorly "
                        f"(~${total_cache_waste:.2f} reclaimable). Worst: {worst_note}."
                    ),
                    impact_usd=round(total_cache_waste, 2),
                    recommendation=(
                        "Low priority; the overall picture is fine. These outliers are "
                        "usually short sessions where the cache never warms (a one-off "
                        "command, an immediate exit). If any are real, recurring tasks, "
                        "give them a stable prefix; otherwise leave them."
                    ),
                )
            )

    rereaders = [m for m in metrics if m.reread_files]
    if rereaders:
        examples = []
        total_reread = 0
        for m in rereaders[:5]:
            for f, n in list(m.reread_files.items())[:2]:
                examples.append(f"{f.split('/')[-1]} x{n}")
                total_reread += n - 1
        out.append(
            Finding(
                id="file-reread-churn",
                title="Files re-read repeatedly within a session",
                severity="medium",
                category="tokens",
                evidence=f"{_sess(len(rereaders))} re-read the same file >= "
                f"{THRESHOLDS['reread_count']}x. Examples: " + ", ".join(examples[:6]),
                impact_usd=round(cost_usd(_tok(total_reread * 4000), 0, 0, 0, price), 2),
                recommendation=(
                    "Read a file once and keep it in working context; widen the first "
                    "read instead of paging back. Add a note to the agent instructions: "
                    "'do not re-Read a file you already loaded this session.'"
                ),
            )
        )

    big = [m for m in metrics if m.big_outputs]
    if big:
        out.append(
            Finding(
                id="oversized-tool-output",
                title="Unbounded tool outputs flood the context window",
                severity="medium",
                category="tokens",
                evidence=f"{sum(m.big_outputs for m in big)} tool results exceeded "
                f"{THRESHOLDS['big_output_chars']:,} chars (~"
                f"{_tok(THRESHOLDS['big_output_chars']):,} tokens each).",
                impact_usd=round(cost_usd(_tok(sum(m.big_outputs for m in big) * THRESHOLDS['big_output_chars']), 0, 0, 0, price), 2),
                recommendation=(
                    "Cap noisy commands (head/tail, --max-count, ripgrep over cat, "
                    "globbed paths). Prefer targeted reads with offset/limit. Pipe "
                    "long logs to a file and grep it instead of dumping to context."
                ),
            )
        )

    retriers = [m for m in metrics if m.repeated_cmds]
    if retriers:
        out.append(
            Finding(
                id="command-retry-loops",
                title="Identical commands re-run (retry loops)",
                severity="low",
                category="tokens",
                evidence=f"{_sess(len(retriers))} repeated an identical Bash command "
                f">= {THRESHOLDS['retry_identical_cmds']}x, a signal of trial-and-error.",
                impact_usd=0.0,
                recommendation=(
                    "Encode the working invocation as a documented command or script so "
                    "the agent does not rediscover it each run. Add failing-fast guards."
                ),
            )
        )

    deniers = [m for m in metrics if m.denial_ratio > THRESHOLDS["high_denial_ratio"]]
    if deniers:
        out.append(
            Finding(
                id="permission-and-error-friction",
                title="High tool-error / permission-denial rate",
                severity="low",
                category="tokens",
                evidence=f"{_sess(len(deniers))} had a tool-error ratio above "
                f"{THRESHOLDS['high_denial_ratio']*100:.0f}%.",
                impact_usd=0.0,
                recommendation=(
                    "Pre-approve the safe, frequently-used commands in settings to cut "
                    "round-trips; fix the recurring failing invocations at the source."
                ),
            )
        )

    compactors = [m for m in metrics if m.compactions >= THRESHOLDS["compaction_warn"]]
    if compactors:
        out.append(
            Finding(
                id="context-thrash",
                title="Frequent compaction signals context bloat",
                severity="medium",
                category="tokens",
                evidence=f"{_sess(len(compactors))} compacted >= "
                f"{THRESHOLDS['compaction_warn']}x, losing working memory mid-task.",
                impact_usd=0.0,
                recommendation=(
                    "Trim always-loaded instructions and docs; move rarely-needed "
                    "reference behind on-demand loads. Smaller standing context means "
                    "fewer compactions and less re-establishing of state."
                ),
            )
        )

    out.sort(key=lambda f: (-_SEV_RANK.get(f.severity, 0), -f.impact_usd))
    return out


_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}
