"""Deterministic repository structure + hygiene scanner (the "improve repo" intent).

Finds, with zero LLM tokens, the things that bloat a repo and slow the agents
working in it: junk/dead artifacts, oversized files, exact-duplicate files
(copy-paste slop), orphaned source modules nothing imports, and the AI-slop
tells (commented-out blocks, duplicate basenames). Everything is a *candidate*
with evidence; nothing is deleted here.

Trust comes from precision: generated, vendored, minified, and test/config files
are classified and excluded from the slop/orphan signals (see ``config.py``), so
the tool does not cry wolf. Performance: a single O(total-bytes) pass builds the
reference index, keeping orphan detection off the O(files^2) path.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import (
    ScanConfig, is_config_file, is_test_file, is_vendored_for_findings,
    looks_generated, looks_minified,
)
from .findings import Finding

SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rs", ".css", ".scss"}
DOC_EXT = {".md", ".mdx", ".txt", ".rst"}
TEXT_EXT = SOURCE_EXT | DOC_EXT | {".json", ".yml", ".yaml", ".toml", ".sql"}

JUNK_NAMES = {".DS_Store", "Thumbs.db", "npm-debug.log", "yarn-error.log", ".env.local.bak"}
JUNK_EXT = {".orig", ".rej", ".bak", ".tmp", ".swp", ".pyc"}
JUNK_DIRS = {"node_modules", ".git", ".next", "dist", "build", "coverage", ".turbo",
             ".cache", "out", ".venv", "__pycache__"}

BIG_FILE_LINES = 700
HUGE_FILE_BYTES = 400_000
DUP_MIN_BYTES = 200
NEAR_DUP_MIN_BYTES = 800   # near-dup needs more substance to be meaningful
COMMENT_BLOCK_MIN = 10


@dataclass
class RepoSummary:
    files: int = 0
    bytes: int = 0
    scanned_source: int = 0
    excluded_generated: int = 0
    junk_count: int = 0
    reclaimable_bytes: int = 0
    largest_file: str = "-"
    largest_bytes: int = 0
    orphan_candidates: int = 0
    duplicate_groups: int = 0


def _tracked_files(repo: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
        files = [repo / line for line in out.splitlines() if line.strip()]
        if files:
            return files
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    files = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in JUNK_DIRS]
        for n in names:
            files.append(Path(root) / n)
    return files


def _area(rel: str) -> str:
    return rel.split("/", 1)[0] if "/" in rel else "."


def _is_junk(name: str, suffix: str) -> bool:
    return name in JUNK_NAMES or suffix in JUNK_EXT or suffix == ".log"


_IMPORT_RE = re.compile(r"""(?:from\s+|require\(\s*|import\(\s*|import\s+)['"]([^'"]+)['"]""")
_REF_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-./@]+")
# A commented-out *code* line: '//' or '#' followed by code-ish punctuation.
_DEAD_CODE_RE = re.compile(r"^\s*(//|#)\s*[\w{}()\[\];=<>.\"'`]")
_JSDOC_RE = re.compile(r"^\s*\*")  # JSDoc continuation, NOT dead code


def _package_json_refs(repo: Path) -> set[str]:
    """Paths referenced by package.json scripts/bin are entrypoints, not orphans."""
    refs: set[str] = set()
    pj = repo / "package.json"
    if not pj.exists():
        return refs
    try:
        import json as _json
        data = _json.loads(pj.read_text())
    except (OSError, ValueError):
        return refs
    blob = " ".join(str(v) for v in (data.get("scripts") or {}).values())
    if isinstance(data.get("bin"), dict):
        blob += " " + " ".join(str(v) for v in data["bin"].values())
    elif isinstance(data.get("bin"), str):
        blob += " " + data["bin"]
    for tok in _REF_TOKEN_RE.findall(blob):
        if "/" in tok and "." in tok.rsplit("/", 1)[-1]:
            refs.add(tok)
    return refs


def _working_tree_changes(repo: Path) -> set[str]:
    """Rel paths with uncommitted changes (modified/added/renamed/untracked).

    These are active, in-flight work, not dead code, so they must never be
    flagged as orphans (an unreferenced module you are mid-edit on is the most
    common false positive, e.g. a new integration not yet wired up).
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return set()
    changed: set[str] = set()
    for line in out.splitlines():
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:  # rename: take the destination
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if path:
            changed.add(path)
    return changed


def scan_repo(repo_path: str, top_n: int = 12) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    cfg = ScanConfig.load(repo)
    files = [f for f in _tracked_files(repo) if f.is_file()]
    changes = _working_tree_changes(repo)

    summary = RepoSummary()
    area_bytes: Counter = Counter()
    sizes: list[tuple[int, str]] = []
    junk: list[str] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    norm_hashes: dict[str, list[str]] = defaultdict(list)  # near-duplicate detection
    # import targets indexed by last path segment for fast, precise resolution
    import_by_stem: dict[str, set[str]] = defaultdict(set)
    # files referenced by bare name (subprocess spawns, lazy-require by filename)
    bare_refs: set[str] = set()
    source_files: list[str] = []
    script_entrypoints: set[str] = set()  # shebang or package.json scripts
    comment_block_files: list[tuple[str, int]] = []
    big_files: list[tuple[str, int]] = []
    basename_dirs: dict[str, set[str]] = defaultdict(set)

    for ref in _package_json_refs(repo):
        _index_ref(ref, import_by_stem)

    for f in files:
        try:
            size = f.stat().st_size
            rel = str(f.relative_to(repo))
        except (OSError, ValueError):
            continue
        name, suffix = f.name, f.suffix.lower()
        summary.files += 1
        summary.bytes += size
        area_bytes[_area(rel)] += size
        sizes.append((size, rel))

        if _is_junk(name, suffix):
            junk.append(rel)
            summary.reclaimable_bytes += size
            continue

        if cfg.is_ignored(rel):
            continue

        ext = suffix
        is_source = ext in SOURCE_EXT
        is_text = ext in TEXT_EXT

        if is_text and size < HUGE_FILE_BYTES:
            try:
                data = f.read_bytes()
            except OSError:
                data = b""
            if not data:
                continue
            text = data.decode("utf-8", "replace")

            # ALWAYS index references first: generated/minified files (barrels,
            # dynamic-import registries) still point at real modules, and
            # dropping them here is what creates orphan false-positives.
            for m in _IMPORT_RE.finditer(text):
                _index_ref(m.group(1), import_by_stem)
            # Path-like string literals (dynamic-import registries, lazy maps),
            # and bare-filename references (subprocess spawns by script name).
            for tok in _REF_TOKEN_RE.findall(text):
                if "/" in tok:
                    _index_ref(tok, import_by_stem)
                else:
                    last = tok.rsplit(".", 1)
                    if len(last) == 2 and last[1] in ("ts", "tsx", "js", "jsx", "mjs", "cjs"):
                        bare_refs.add(last[0])

            # Generated/minified files are excluded from being *findings targets*
            # (not from the reference index above).
            if looks_generated(text) or looks_minified(text):
                summary.excluded_generated += 1
                continue

            # Vendored skill/plugin internals: references already indexed above;
            # do not treat them as refactoring targets.
            if is_vendored_for_findings(rel):
                continue

            if size >= DUP_MIN_BYTES:
                hashes[hashlib.sha1(data).hexdigest()].append(rel)
                # Near-duplicate: hash structure-only content (whitespace, blank
                # lines, comments, and import lines stripped) so reformatted or
                # reordered copy-paste still collides. Bigger floor to avoid noise.
                if is_source and size >= NEAR_DUP_MIN_BYTES:
                    norm = _normalize_source(text)
                    if norm:
                        norm_hashes["%s:%s" % (suffix, hashlib.sha1(norm.encode()).hexdigest())].append(rel)

            if is_source:
                if text.startswith("#!"):
                    script_entrypoints.add(rel)
                source_files.append(rel)
                basename_dirs[f.stem].add(rel.rsplit("/", 1)[0] if "/" in rel else ".")
                summary.scanned_source += 1
                worst = _dead_code_run(text)
                if worst >= COMMENT_BLOCK_MIN:
                    comment_block_files.append((rel, worst))
                nlines = text.count("\n") + 1
                if nlines >= BIG_FILE_LINES:
                    big_files.append((rel, nlines))

    if sizes:
        big_size, big_rel = max(sizes, key=lambda t: t[0])
        summary.largest_bytes = big_size
        summary.largest_file = big_rel

    code_dups, doc_dups = [], []
    for paths in hashes.values():
        if len(paths) <= 1:
            continue
        if paths[0].rsplit(".", 1)[-1] in ("md", "mdx", "txt", "rst"):
            doc_dups.append(paths)
        else:
            code_dups.append(paths)
    # near-duplicates: same normalized structure, but NOT already exact dups
    exact_members = {p for g in code_dups + doc_dups for p in g}
    near_dups = []
    for paths in norm_hashes.values():
        if len(paths) > 1 and not all(p in exact_members for p in paths):
            near_dups.append(paths)

    summary.duplicate_groups = len(code_dups) + len(doc_dups)
    dup_reclaim = 0
    for g in code_dups + doc_dups:
        try:
            dup_reclaim += (len(g) - 1) * (repo / g[0]).stat().st_size
        except OSError:
            pass
    summary.reclaimable_bytes += dup_reclaim

    lib_orphans, script_orphans = [], []
    for rel in source_files:
        stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if is_test_file(rel) or is_config_file(stem) or rel in script_entrypoints:
            continue
        if rel in changes:  # active, uncommitted work is not dead code
            continue
        if stem in bare_refs:
            continue
        if _is_referenced(rel, stem, import_by_stem):
            continue
        if _is_script_area(rel):
            script_orphans.append(rel)
        else:
            lib_orphans.append(rel)
    summary.orphan_candidates = len(lib_orphans)
    summary.junk_count = len(junk) + summary.duplicate_groups

    findings = _repo_findings(junk, code_dups, doc_dups, near_dups, lib_orphans,
                              script_orphans, big_files, comment_block_files,
                              basename_dirs, summary)
    health = _health_score(summary)
    size_by_area = [{"label": a, "bytes": b} for a, b in area_bytes.most_common(top_n)]

    return {
        "repo": str(repo),
        "summary": asdict(summary),
        "size_by_area": size_by_area,
        "health_score": health,
        "findings": [f.to_dict() for f in findings],
    }


def _normalize_source(text: str) -> str:
    """Strip formatting/comment/import noise so near-identical code collides.

    Keeps only structural lines, lowercased and whitespace-collapsed, so two
    files that differ by blank lines, reordered imports, or reformatting still
    hash the same. Conservative: drops nothing structural.
    """
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("//", "#", "*", "/*", "*/")):
            continue
        if s.startswith("import ") or s.startswith("export {") or s.startswith("from "):
            continue
        out.append(" ".join(s.split()).lower())
    return "\n".join(out)


def _dead_code_run(text: str) -> int:
    run = worst = 0
    for line in text.splitlines():
        if _DEAD_CODE_RE.match(line) and not _JSDOC_RE.match(line):
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def _norm_import(ip: str) -> str | None:
    """Normalize an import/path specifier to a comparable, extensionless suffix.

    Drops alias (`@/`), relative prefixes, and the extension. Returns None for
    bare package specifiers (no slash, e.g. `react`), which never name a repo file.
    """
    p = ip.strip()
    if "/" not in p:
        return None
    while p.startswith("./") or p.startswith("../"):
        p = p.split("/", 1)[1]
    p = p.lstrip("@").lstrip("/")
    # strip a trailing extension if it looks like one
    last = p.rsplit("/", 1)[-1]
    if "." in last and last.rsplit(".", 1)[-1] in ("ts", "tsx", "js", "jsx", "mjs", "cjs", "css", "scss", "json"):
        p = p.rsplit(".", 1)[0]
    return p or None


def _index_ref(ip: str, index: dict[str, set[str]]) -> None:
    norm = _norm_import(ip)
    if not norm:
        return
    stem = norm.rsplit("/", 1)[-1]
    index[stem].add(norm)


def _is_referenced(rel: str, stem: str, index: dict[str, set[str]]) -> bool:
    """A file is referenced only if some import target *resolves to its path*.

    Matching is by extensionless path suffix (not bare stem), so an incidental
    mention of the same filename elsewhere does not mask a genuinely dead module.
    """
    relne = rel.rsplit(".", 1)[0]
    targets = index.get(stem)
    if not targets:
        return False
    for norm in targets:
        if relne == norm or relne.endswith("/" + norm) or norm.endswith("/" + relne):
            return True
    return False


_SCRIPT_AREAS = ("scripts/", ".claude/", "bin/", "tools/", "tasks/", ".github/")


def _is_script_area(rel: str) -> bool:
    return any(rel.startswith(a) or ("/" + a) in ("/" + rel) for a in _SCRIPT_AREAS)


def _repo_findings(junk, code_dups, doc_dups, near_dups, orphans, script_orphans,
                   big_files, comment_block_files, basename_dirs, summary) -> list[Finding]:
    out: list[Finding] = []

    if junk:
        out.append(Finding(
            id="junk-artifacts",
            title="Committed junk / build artifacts",
            severity="high" if len(junk) > 5 else "medium",
            category="repo",
            evidence=f"{_n(len(junk),'junk file','junk files')} tracked (logs, .DS_Store, .orig/.bak/.tmp).",
            recommendation="Remove and add to .gitignore. These inflate clones and every agent's file listing.",
            locations=junk[:10], effort="trivial", autofixable=True, tags=["hygiene"],
        ))

    if code_dups:
        examples = ["==".join(p.rsplit("/", 1)[-1] for p in g[:3]) for g in code_dups[:4]]
        out.append(Finding(
            id="duplicate-code",
            title="Exact-duplicate source files (copy-paste slop)",
            severity="medium",
            category="repo",
            evidence=f"{_n(len(code_dups),'group','groups')} of byte-identical source files. e.g. " + "; ".join(examples),
            recommendation="Collapse to one shared module and import it. Duplicates drift and double the read cost for agents.",
            locations=[g[0] for g in code_dups[:8]], effort="small", tags=["dedupe", "slop"],
        ))

    if doc_dups:
        out.append(Finding(
            id="duplicate-docs",
            title="Duplicate documentation files",
            severity="low",
            category="repo",
            evidence=f"{_n(len(doc_dups),'group','groups')} of byte-identical doc files (often stale template copies).",
            recommendation="Keep one canonical doc and link to it; delete the copies so agents do not read the same content N times.",
            locations=[g[0] for g in doc_dups[:8]], effort="trivial", tags=["docs"],
        ))

    if near_dups:
        examples = ["~".join(p.rsplit("/", 1)[-1] for p in g[:3]) for g in near_dups[:4]]
        out.append(Finding(
            id="near-duplicate-code",
            title="Near-duplicate source files (AI-slop copy-paste)",
            severity="low",
            category="repo",
            evidence=f"{_n(len(near_dups),'group','groups')} of files with identical structure "
            f"ignoring formatting/imports/comments. e.g. " + "; ".join(examples),
            recommendation="These are copy-paste-then-tweak clones, the classic AI-slop pattern. "
            "Extract the shared logic into one parameterized module; the variants drift apart and "
            "multiply every future edit and read.",
            locations=[g[0] for g in near_dups[:8]], effort="medium", tags=["slop", "dedupe"],
        ))

    if orphans:
        out.append(Finding(
            id="orphan-modules",
            title="Orphan library modules (no inbound imports)",
            severity="medium" if len(orphans) > 3 else "low",
            category="repo",
            evidence=f"{_n(len(orphans),'library module','library modules')} under app/components/lib appear unreferenced (candidates; verify dynamic imports first).",
            recommendation="Confirm with knip/ts-prune, then delete behind a typecheck+lint gate. Dead modules tax every repo-wide search.",
            locations=orphans[:12], effort="medium", tags=["dead-code"],
        ))

    if script_orphans:
        out.append(Finding(
            id="unreferenced-scripts",
            title="Standalone scripts with no inbound imports",
            severity="info",
            category="repo",
            evidence=f"{_n(len(script_orphans),'script','scripts')} in scripts/.claude/tasks have no importer (usually intentional CLI entrypoints, but obsolete one-offs hide here).",
            recommendation="Triage: keep documented entrypoints, archive obsolete one-off backfills/migrations so future agents do not read or grep them.",
            locations=script_orphans[:12], effort="small", tags=["dead-code", "scripts"],
        ))

    if big_files:
        big_files.sort(key=lambda t: -t[1])
        out.append(Finding(
            id="oversized-files",
            title="Oversized source files",
            severity="low",
            category="repo",
            evidence=f"{_n(len(big_files),'file','files')} exceed {BIG_FILE_LINES} lines; the largest is {big_files[0][1]:,} lines.",
            recommendation="Split god-files by responsibility. Smaller files mean cheaper, more precise agent reads and edits.",
            locations=[f"{rel} ({n:,} lines)" for rel, n in big_files[:8]], effort="medium", tags=["structure"],
        ))

    if comment_block_files:
        out.append(Finding(
            id="commented-out-code",
            title="Large commented-out code blocks",
            severity="low",
            category="repo",
            evidence=f"{_n(len(comment_block_files),'file','files')} contain a commented-out code block of >= {COMMENT_BLOCK_MIN} lines.",
            recommendation="Delete dead code; git history is the archive. Commented blocks mislead agents and bloat context.",
            locations=[rel for rel, _ in comment_block_files[:8]], effort="trivial", autofixable=True, tags=["slop"],
        ))

    scattered = {k: v for k, v in basename_dirs.items() if len(v) >= 4}
    if scattered:
        out.append(Finding(
            id="ambiguous-basenames",
            title="Same filename scattered across many directories",
            severity="info",
            category="repo",
            evidence=f"{_n(len(scattered),'basename','basenames')} live in 4+ directories (e.g. " + ", ".join(sorted(scattered)[:5]) + ").",
            recommendation="Disambiguate names or co-locate. Unique, descriptive paths cut the agent's search-and-guess loops.",
            effort="small", tags=["naming"],
        ))

    out.sort(key=lambda f: (-_SEV.get(f.severity, 0), -len(f.locations)))
    return out


_SEV = {"high": 3, "medium": 2, "low": 1, "info": 0}


def _n(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _health_score(s: RepoSummary) -> float:
    score = 100.0
    score -= min(30, s.junk_count * 4)
    score -= min(18, s.orphan_candidates * 1.5)
    score -= min(16, s.duplicate_groups * 3)
    if s.bytes:
        score -= min(12, (s.reclaimable_bytes / s.bytes) * 100)
    return round(max(0.0, score), 1)
