"""Command-line entrypoint for the session analyzer.

Subcommands:
  analyze   run a full pass (tokens | repo | both) and render a report
  extract   emit the deterministic metrics + a token-bounded agent digest only
  render    re-render a saved run bundle (terminal or markdown)
  map       generate an orientation CLAUDE.md (the proven token lever)

The deterministic pass needs no agent. The optional synthesis step is driven by
the SKILL.md instructions, which read the small digest this CLI writes and append
tailored findings before a final `render`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .budget import Budget, cap_for_mode
from .digest import write_digest
from .extract import build_token_report
from .pricing import DEFAULT_PRICE, Price
from .render import render_markdown, render_terminal
from .report import combined_bundle, repo_bundle, token_bundle
from .repo_scan import scan_repo
from .sessions import load_sessions
from .theme import make_style


def _price(args) -> Price:
    return Price(
        input_per_mtok=args.price_input,
        output_per_mtok=args.price_output,
        cache_read_per_mtok=args.price_cache_read,
        cache_write_per_mtok=args.price_cache_write,
    )


def _run_token(args, price) -> dict:
    from dataclasses import asdict

    sessions = load_sessions(
        projects_root=Path(args.projects_root) if args.projects_root else None,
        project_filter=args.repo if args.scope_repo else None,
        limit=args.max_sessions,
        since_days=args.since,
    )
    return asdict(build_token_report(sessions, price=price, top_n=args.top))


def _run_repo(args) -> dict:
    return scan_repo(args.repo or ".", top_n=args.top)


def cmd_analyze(args) -> int:
    price = _price(args)
    mode = args.mode
    bundle = None
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    token_rep = repo_rep = None
    if mode in ("tokens", "both"):
        token_rep = _run_token(args, price)
    if mode in ("repo", "both"):
        repo_rep = _run_repo(args)

    if mode == "tokens":
        bundle = token_bundle(token_rep)
    elif mode == "repo":
        bundle = repo_bundle(repo_rep)
    else:
        bundle = combined_bundle(token_rep, repo_rep)

    if out_dir:
        if token_rep:
            (out_dir / "token_report.json").write_text(json.dumps(token_rep, indent=2))
        if repo_rep:
            (out_dir / "repo_report.json").write_text(json.dumps(repo_rep, indent=2))
        (out_dir / "bundle.json").write_text(json.dumps(bundle, indent=2))
        (out_dir / "report.md").write_text(render_markdown(bundle))
        cap = cap_for_mode(mode, args.budget)
        budget = Budget(cap_tokens=cap)
        write_digest(out_dir, bundle, token_rep, repo_rep, budget)
        budget.save(out_dir / "budget.json")

    _emit(args, bundle)
    return _gate(args, bundle)


_GRADE_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


def _gate(args, bundle) -> int:
    """Return a non-zero exit code if a CI grade threshold is set and missed."""
    want = getattr(args, "fail_under", None)
    if not want:
        return 0
    grade = (bundle.get("verdict", {}).get("grade") or "")[:1].upper()
    got = _GRADE_RANK.get(grade, 0)
    need = _GRADE_RANK.get(want[:1].upper(), 0)
    if got and got < need:
        print(f"\n[fail-under] grade {grade} is below required {want.upper()}", file=sys.stderr)
        return 1
    return 0


def _emit(args, bundle) -> None:
    if args.format == "json":
        print(json.dumps(bundle, indent=2))
    elif args.format == "markdown":
        print(render_markdown(bundle))
    else:
        st = make_style(force=True if args.color == "always" else False if args.color == "never" else None)
        print(render_terminal(bundle, st))


def cmd_doctor(args) -> int:
    """Show what the analyzer can see, the fastest way to debug discovery."""
    from .sessions import default_projects_root, iter_transcript_files
    root = Path(args.projects_root) if args.projects_root else default_projects_root()
    st = make_style()
    print(st.role("session-analyzer doctor", "accent", bold=True))
    print(f"  projects root : {root}")
    print(f"  exists        : {root.exists()}")
    files = list(iter_transcript_files(root))
    print(f"  transcripts   : {len(files)}")
    projects = sorted({p.parent.name for p in files})
    for proj in projects[:20]:
        n = sum(1 for p in files if p.parent.name == proj)
        print(f"    {proj}  ({n})")
    if not files:
        print(st.role("  No transcripts found.", "medium"))
        print("  Tip: set CLAUDE_CONFIG_DIR or pass --projects-root, and run a session first.")
    return 0


def cmd_extract(args) -> int:
    args.out = args.out or ".sa/run"
    args.format = "markdown" if args.format == "markdown" else "terminal"
    # extract = analyze but quiet, emitting artifacts for the agent stage
    rc = cmd_analyze(args)
    print(f"\n[extract] artifacts written to {args.out}", file=sys.stderr)
    return rc


_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}


def _merge_synthesis(bundle: dict, path: Path) -> int:
    """Fold agent-written synthesis findings into a bundle and re-sort by severity.

    Accepts a JSON list of findings, or an object with a "findings" list. A
    synthesis finding whose id matches a deterministic one replaces it.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return 0
    extra = data if isinstance(data, list) else data.get("findings", [])
    if not isinstance(extra, list) or not extra:
        return 0
    base = bundle.get("findings")
    base = base if isinstance(base, list) else []
    by_id: dict = {}
    order: list = []
    for f in base + extra:
        if not isinstance(f, dict):
            continue
        key = f.get("id") or len(order)
        if key not in by_id:
            order.append(key)
        by_id[key] = f
    merged = [by_id[k] for k in order]
    merged.sort(key=lambda f: -_SEV_RANK.get(f.get("severity", ""), 0))
    bundle["findings"] = merged
    return len(extra)


def cmd_map(args) -> int:
    """Generate an orientation CLAUDE.md for a repo (the proven token lever).

    SA-Bench measures the orientation map as a Pareto win (~41-47% fewer tokens,
    quality held). This emits one deterministically instead of having the agent
    re-derive it from scratch each run.
    """
    from .orient import build_map, render_map

    m = build_map(args.repo, max_modules=args.max_modules, verify_cmd=args.verify_cmd)
    if args.format == "json":
        print(json.dumps(m, indent=2))
        return 0
    text = render_map(m)
    if args.out:
        out_path = Path(args.out)
        if out_path.is_dir():
            out_path = out_path / "CLAUDE.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        print(f"[map] wrote orientation map ({len(m['modules'])} modules) to {out_path}",
              file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_render(args) -> int:
    bundle_path = Path(args.bundle)
    bundle = json.loads(bundle_path.read_text())
    syn = getattr(args, "synthesis", None)
    syn_path = Path(syn) if syn else bundle_path.parent / "synthesis.json"
    merged = _merge_synthesis(bundle, syn_path) if syn_path.exists() else 0
    _emit(args, bundle)
    if merged:
        print(f"\n[render] merged {merged} synthesis finding(s) from {syn_path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analyze", description="Claude session-history analyzer")
    p.add_argument("--version", action="version", version=f"session-analyzer {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--mode", choices=["tokens", "repo", "both"], default="tokens")
        sp.add_argument("--repo", default=".", help="target repo path (repo intent + session scoping)")
        sp.add_argument("--scope-repo", action="store_true", help="limit sessions to --repo")
        sp.add_argument("--projects-root", default=None, help="override ~/.claude/projects")
        sp.add_argument("--max-sessions", type=int, default=None)
        sp.add_argument("--since", type=float, default=None, metavar="DAYS",
                        help="only sessions modified within DAYS")
        sp.add_argument("--fail-under", default=None, metavar="GRADE",
                        help="exit non-zero if the grade is worse than this (A-F), for CI gating")
        sp.add_argument("--top", type=int, default=12)
        sp.add_argument("--budget", type=int, default=None, help="token cap override")
        sp.add_argument("--out", default=None, help="write run artifacts here")
        sp.add_argument("--format", choices=["terminal", "markdown", "json"], default="terminal")
        sp.add_argument("--color", choices=["auto", "always", "never"], default="auto")
        sp.add_argument("--price-input", type=float, default=DEFAULT_PRICE.input_per_mtok)
        sp.add_argument("--price-output", type=float, default=DEFAULT_PRICE.output_per_mtok)
        sp.add_argument("--price-cache-read", type=float, default=DEFAULT_PRICE.cache_read_per_mtok)
        sp.add_argument("--price-cache-write", type=float, default=DEFAULT_PRICE.cache_write_per_mtok)

    a = sub.add_parser("analyze", help="full pass + render")
    common(a)
    a.set_defaults(func=cmd_analyze)

    e = sub.add_parser("extract", help="deterministic pass + agent digest")
    common(e)
    e.set_defaults(func=cmd_extract)

    r = sub.add_parser("render", help="re-render a saved bundle.json (auto-merges a sibling synthesis.json)")
    r.add_argument("bundle")
    r.add_argument("--synthesis", default=None,
                   help="agent findings to merge (default: synthesis.json next to the bundle)")
    r.add_argument("--format", choices=["terminal", "markdown", "json"], default="terminal")
    r.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    r.set_defaults(func=cmd_render)

    d = sub.add_parser("doctor", help="show discoverable sessions / projects")
    d.add_argument("--projects-root", default=None)
    d.set_defaults(func=cmd_doctor)

    m = sub.add_parser("map", help="generate an orientation CLAUDE.md (the proven token lever)")
    m.add_argument("--repo", default=".", help="repo to map (default: cwd)")
    m.add_argument("--out", default=None,
                   help="write the map here (a dir gets CLAUDE.md); default: stdout")
    m.add_argument("--max-modules", type=int, default=40,
                   help="cap the number of modules listed (default: 40)")
    m.add_argument("--verify-cmd", default=None,
                   help="override the auto-detected verify command")
    m.add_argument("--format", choices=["markdown", "json"], default="markdown")
    m.set_defaults(func=cmd_map)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
