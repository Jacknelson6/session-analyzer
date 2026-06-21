"""Discovery and parsing of Claude Code session transcripts (.jsonl).

Claude Code writes one transcript per session under:

    ~/.claude/projects/<path-encoded-cwd>/<session-uuid>.jsonl

Each line is a JSON object. The shapes we rely on (verified against real
transcripts) are documented in ``docs/transcript-schema.md``. This module is
intentionally defensive: transcript schemas drift across CLI versions, so every
field access is guarded and unknown event types are ignored rather than fatal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


def default_projects_root() -> Path:
    """Return the Claude projects root, honoring CLAUDE_CONFIG_DIR."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    if base:
        return Path(base).expanduser() / "projects"
    return Path.home() / ".claude" / "projects"


def encode_project_dir(cwd: str) -> str:
    """Claude encodes a project path by replacing path separators with '-'.

    e.g. ``/home/user/acme-app`` -> ``-home-user-acme-app``.
    """
    return cwd.replace("/", "-")


def iter_transcript_files(
    projects_root: Path | None = None,
    project_filter: str | None = None,
) -> Iterator[Path]:
    """Yield every transcript .jsonl under the projects root.

    ``project_filter`` matches a substring of the encoded project directory
    name, so passing a repo path or its basename scopes discovery to one repo.
    """
    root = projects_root or default_projects_root()
    if not root.exists():
        return
    needle = None
    if project_filter:
        needle = encode_project_dir(os.path.abspath(project_filter))
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        if needle and needle not in project_dir.name and os.path.basename(project_filter) not in project_dir.name:
            continue
        for jsonl in sorted(project_dir.glob("*.jsonl")):
            yield jsonl


@dataclass
class Turn:
    """One assistant or user event from a transcript, normalized."""

    role: str  # "assistant" | "user" | other
    ts: str | None
    git_branch: str | None
    cwd: str | None
    permission_mode: str | None
    # token usage (assistant turns only)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    # content signals
    tool_calls: list[str] = field(default_factory=list)
    tool_inputs: list[dict[str, Any]] = field(default_factory=list)
    tool_errors: int = 0
    tool_result_chars: list[int] = field(default_factory=list)
    is_compaction: bool = False
    is_sidechain: bool = False
    text_chars: int = 0
    thinking_chars: int = 0

    @property
    def billable_input(self) -> int:
        """Tokens actually charged at full input rate (cache misses)."""
        return self.input_tokens

    @property
    def total_input_context(self) -> int:
        """Full prompt size: fresh + cache-read + cache-creation."""
        return self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens


@dataclass
class Session:
    """A parsed transcript: ordered turns plus convenience rollups."""

    session_id: str
    path: Path
    turns: list[Turn] = field(default_factory=list)
    cwd: str | None = None
    git_branch: str | None = None
    started: str | None = None
    ended: str | None = None
    version: str | None = None

    @property
    def assistant_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "assistant"]

    @property
    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _iter_lines(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _parse_usage(msg: dict[str, Any], turn: Turn) -> None:
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return
    turn.input_tokens = _as_int(usage.get("input_tokens"))
    turn.output_tokens = _as_int(usage.get("output_tokens"))
    turn.cache_read_tokens = _as_int(usage.get("cache_read_input_tokens"))
    turn.cache_creation_tokens = _as_int(usage.get("cache_creation_input_tokens"))


def _parse_content(msg: dict[str, Any], turn: Turn) -> None:
    content = msg.get("content")
    if isinstance(content, str):
        turn.text_chars += len(content)
        return
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "tool_use":
            name = block.get("name") or "unknown"
            turn.tool_calls.append(name)
            inp = block.get("input")
            turn.tool_inputs.append(inp if isinstance(inp, dict) else {})
        elif btype == "tool_result":
            if block.get("is_error"):
                turn.tool_errors += 1
            rc = block.get("content")
            if isinstance(rc, str):
                turn.tool_result_chars.append(len(rc))
            elif isinstance(rc, list):
                total = sum(len(b.get("text") or "") for b in rc if isinstance(b, dict))
                turn.tool_result_chars.append(total)
        elif btype == "text":
            turn.text_chars += len(block.get("text") or "")
        elif btype == "thinking":
            turn.thinking_chars += len(block.get("thinking") or "")


def parse_session(path: Path) -> Session:
    """Parse a single transcript into a Session."""
    sid = path.stem
    session = Session(session_id=sid, path=path)
    for event in _iter_lines(path):
        etype = event.get("type")
        ts = event.get("timestamp")
        if ts:
            session.ended = ts
            if session.started is None:
                session.started = ts
        if session.cwd is None and event.get("cwd"):
            session.cwd = event.get("cwd")
        if event.get("gitBranch"):
            session.git_branch = event.get("gitBranch")
        if session.version is None and event.get("version"):
            session.version = event.get("version")

        if etype not in ("assistant", "user"):
            continue
        msg = event.get("message")
        if not isinstance(msg, dict):
            continue
        turn = Turn(
            role=etype,
            ts=ts,
            git_branch=event.get("gitBranch"),
            cwd=event.get("cwd"),
            permission_mode=event.get("permissionMode"),
            is_sidechain=bool(event.get("isSidechain")),
        )
        # Compaction events are surfaced as a synthetic user turn in some CLI
        # versions; detect by subtype or marker text.
        if event.get("subtype") == "compact_boundary" or event.get("isCompactSummary"):
            turn.is_compaction = True
        if etype == "assistant":
            _parse_usage(msg, turn)
        _parse_content(msg, turn)
        session.turns.append(turn)
    return session


def load_sessions(
    projects_root: Path | None = None,
    project_filter: str | None = None,
    limit: int | None = None,
    since_days: float | None = None,
) -> list[Session]:
    """Discover and parse sessions, newest file first.

    ``since_days`` keeps only transcripts modified within that many days, the
    cheap way to ask "what changed this week".
    """
    import time

    files = list(iter_transcript_files(projects_root, project_filter))
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if since_days is not None:
        cutoff = time.time() - since_days * 86400
        files = [p for p in files if p.exists() and p.stat().st_mtime >= cutoff]
    if limit:
        files = files[:limit]
    return [parse_session(p) for p in files]
