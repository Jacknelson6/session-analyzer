"""Deterministic orientation-map generator (the proven token lever).

SA-Bench measured the orientation map as a Pareto win: ~41-47% fewer tokens with
output quality held (see ``bench/``). The map works because it lets the agent
trust an authoritative file/symbol index instead of re-exploring the tree turn
after turn. Until now the tool only *advised* writing one; the agent hand-rolled
it from the digest every run, which costs tokens and varies in quality.

This module emits that map deterministically, in the exact format the benchmark
validated: a per-module index of the public surface, plus a short workflow
section (read-once rule + a single detected verify command). Zero model tokens.

Python surfaces are read with the stdlib ``ast`` (exact); JS/TS/Go/Rust are read
with conservative export regexes. Generated, vendored, minified, and junk files
are excluded so the map stays an authoritative index of the code the user owns.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .config import is_vendored_for_findings, looks_generated, looks_minified
from .repo_scan import JUNK_EXT, JUNK_NAMES, _is_junk, _tracked_files

# Extensions we can describe a public surface for, in display priority order.
PY_EXT = {".py"}
JSTS_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
GO_EXT = {".go"}
RUST_EXT = {".rs"}
MAP_EXT = PY_EXT | JSTS_EXT | GO_EXT | RUST_EXT

DEFAULT_MAX_MODULES = 40
MAX_SYMBOLS_PER_MODULE = 14   # keep the map small; a god-file can't bloat it
MAX_FIELDS_PER_CLASS = 10
# Directories whose files are entrypoints/config noise, mapped last or not at all.
_LOW_PRIORITY_DIRS = ("scripts/", "tools/", "tasks/", ".github/", "examples/")


# --------------------------------------------------------------------------- #
# Python surface extraction (exact, via ast)
# --------------------------------------------------------------------------- #

def _fmt_args(node: ast.arguments) -> str:
    """Render a function signature's args, dropping self/cls, keeping defaults."""
    parts: list[str] = []
    posonly = list(getattr(node, "posonlyargs", []))
    args = posonly + list(node.args)
    defaults = list(node.defaults)
    n_defaults = len(defaults)
    first_default = len(args) - n_defaults
    for i, a in enumerate(args):
        if a.arg in ("self", "cls"):
            continue
        if i >= first_default:
            parts.append(f"{a.arg}=...")
        else:
            parts.append(a.arg)
    if node.vararg:
        parts.append("*" + node.vararg.arg)
    for a in node.kwonlyargs:
        parts.append(f"{a.arg}=...")
    if node.kwarg:
        parts.append("**" + node.kwarg.arg)
    return ", ".join(parts)


def _is_dataclass(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        name = dec.func.id if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) else getattr(dec, "id", None)
        if name == "dataclass":
            return True
    return False


def _class_fields(node: ast.ClassDef) -> list[str]:
    """Annotated class-level fields (dataclass-style), with `=...` for defaults."""
    fields: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields.append(stmt.target.id + ("=..." if stmt.value is not None else ""))
    return fields


def _class_methods(node: ast.ClassDef) -> list[str]:
    out: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith("_"):
            out.append(f"{stmt.name}({_fmt_args(stmt.args)})")
    return out


def _py_surface(text: str) -> tuple[str, list[str]]:
    """Return (one-line summary, public-symbol descriptions) for a Python module."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "", []
    summary = (ast.get_docstring(tree) or "").strip().splitlines()
    summary_line = summary[0].rstrip(".") if summary else ""

    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            if _is_dataclass(node) or _class_fields(node):
                fields = _class_fields(node)
                if len(fields) > MAX_FIELDS_PER_CLASS:
                    fields = fields[:MAX_FIELDS_PER_CLASS] + ["..."]
                symbols.append(f"`{node.name}({', '.join(fields)})`")
            else:
                methods = _class_methods(node)
                if methods:
                    symbols.append(f"`{node.name}`: " + ", ".join(f"`{m}`" for m in methods))
                else:
                    symbols.append(f"`{node.name}`")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            symbols.append(f"`{node.name}({_fmt_args(node.args)})`")
    return summary_line, symbols


# --------------------------------------------------------------------------- #
# JS / TS / Go / Rust surface extraction (conservative regex)
# --------------------------------------------------------------------------- #

_JS_EXPORT = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:(?:function|class)\s+([A-Za-z0-9_$]+)"
    r"|(?:const|let|var)\s+([A-Za-z0-9_$]+))",
    re.MULTILINE,
)
_GO_EXPORT = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Z][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_GO_TYPE = re.compile(r"^\s*type\s+([A-Z][A-Za-z0-9_]*)\s+", re.MULTILINE)
_RS_PUB = re.compile(r"^\s*pub\s+(?:async\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z0-9_]+)", re.MULTILINE)
_LEADING_COMMENT = re.compile(r"^\s*(?://+|/\*+|#+)\s?(.*)")


def _regex_surface(text: str, ext: str) -> tuple[str, list[str]]:
    summary = ""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _LEADING_COMMENT.match(s)
        if m and m.group(1).strip():
            summary = m.group(1).strip().rstrip("*/").rstrip(".").strip()
        break

    names: list[str] = []
    if ext in JSTS_EXT:
        for m in _JS_EXPORT.finditer(text):
            names.append(m.group(1) or m.group(2))
    elif ext in GO_EXT:
        names.extend(m.group(1) for m in _GO_TYPE.finditer(text))
        names.extend(m.group(1) for m in _GO_EXPORT.finditer(text))
    elif ext in RUST_EXT:
        names.extend(m.group(1) for m in _RS_PUB.finditer(text))

    seen: set[str] = set()
    symbols: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            symbols.append(f"`{n}`")
    return summary, symbols


# --------------------------------------------------------------------------- #
# Verify-command detection
# --------------------------------------------------------------------------- #

def detect_verify_cmd(repo: Path, rels: list[str]) -> str:
    """Best-effort single verify command for the repo's stack."""
    names = {r.rsplit("/", 1)[-1] for r in rels}
    has_py = any(r.endswith(".py") for r in rels)
    has_tests_dir = any(r.startswith("tests/") or "/tests/" in r for r in rels)

    pj = repo / "package.json"
    if pj.exists():
        try:
            import json as _json
            scripts = _json.loads(pj.read_text()).get("scripts", {})
        except (OSError, ValueError):
            scripts = {}
        if "test" in scripts:
            return "npm test"
        if "lint" in scripts:
            return "npm run lint"
    if "Cargo.toml" in names:
        return "cargo test"
    if "go.mod" in names:
        return "go test ./..."
    if has_py:
        pytest_markers = {"pytest.ini", "conftest.py"} & names
        if pytest_markers or _pyproject_has_pytest(repo):
            return "pytest -q"
        if has_tests_dir:
            return "python3 -m unittest discover -s tests -t . -q"
        return "python3 -m unittest -q"
    if "Makefile" in names:
        return "make test"
    return ""


def _pyproject_has_pytest(repo: Path) -> bool:
    pp = repo / "pyproject.toml"
    if not pp.exists():
        return False
    try:
        return "pytest" in pp.read_text()
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Map assembly
# --------------------------------------------------------------------------- #

def _sort_key(rel: str) -> tuple:
    low = any(rel.startswith(d) or ("/" + d) in ("/" + rel) for d in _LOW_PRIORITY_DIRS)
    is_test = "test" in rel.rsplit("/", 1)[-1].lower()
    return (1 if low else 0, 1 if is_test else 0, rel.count("/"), rel)


def build_map(repo_path: str, max_modules: int = DEFAULT_MAX_MODULES,
              verify_cmd: str | None = None) -> dict[str, Any]:
    """Build the orientation map for a repo. Returns a structured dict."""
    repo = Path(repo_path).resolve()
    all_files = [f for f in _tracked_files(repo) if f.is_file()]

    rels = []
    for f in all_files:
        try:
            rels.append(str(f.relative_to(repo)))
        except ValueError:
            continue

    modules: list[dict[str, Any]] = []
    for f in all_files:
        suffix = f.suffix.lower()
        if suffix not in MAP_EXT:
            continue
        try:
            rel = str(f.relative_to(repo))
            data = f.read_bytes()
        except (OSError, ValueError):
            continue
        # Skip anything under a dot-directory (.github, .claude, hidden test/grader
        # dirs): not the source the user works in, and mapping a hidden grader dir
        # would leak its contents.
        if any(part.startswith(".") for part in rel.split("/")[:-1]):
            continue
        if _is_junk(f.name, suffix) or f.name in JUNK_NAMES or suffix in JUNK_EXT:
            continue
        text = data.decode("utf-8", "replace")
        if looks_generated(text) or looks_minified(text) or is_vendored_for_findings(rel):
            continue

        is_test = "test" in rel.rsplit("/", 1)[-1].lower()
        if suffix in PY_EXT:
            summary, symbols = _py_surface(text)
        else:
            summary, symbols = _regex_surface(text, suffix)
        if is_test:
            summary = summary or "test suite"
            symbols = []
        if len(symbols) > MAX_SYMBOLS_PER_MODULE:
            extra = len(symbols) - MAX_SYMBOLS_PER_MODULE
            symbols = symbols[:MAX_SYMBOLS_PER_MODULE] + [f"`+{extra} more`"]
        if not symbols and not summary and not is_test:
            continue
        modules.append({"path": rel, "summary": summary, "symbols": symbols})

    modules.sort(key=lambda m: _sort_key(m["path"]))
    truncated = max(0, len(modules) - max_modules)
    modules = modules[:max_modules]

    cmd = verify_cmd if verify_cmd is not None else detect_verify_cmd(repo, rels)
    return {
        "repo": str(repo),
        "name": repo.name,
        "modules": modules,
        "verify_cmd": cmd,
        "truncated": truncated,
    }


def render_map(m: dict[str, Any]) -> str:
    """Render an orientation map dict as a CLAUDE.md, in the validated format."""
    lines: list[str] = []
    lines.append(f"# {m['name']} — orientation")
    lines.append("")
    lines.append("This map is authoritative; trust it instead of re-exploring the tree.")
    lines.append("")
    for mod in m["modules"]:
        # both present -> "summary: sym, sym"; one present -> just that one
        if mod["summary"] and mod["symbols"]:
            desc = f" — {mod['summary']}: " + ", ".join(mod["symbols"])
        elif mod["symbols"]:
            desc = " — " + ", ".join(mod["symbols"])
        elif mod["summary"]:
            desc = " — " + mod["summary"]
        else:
            desc = ""
        lines.append(f"- `{mod['path']}`{desc}")
    if m.get("truncated"):
        lines.append(f"- (+{m['truncated']} more modules; run a search for anything not listed)")
    lines.append("")
    lines.append("## Workflow")
    lines.append("")
    lines.append("- Read a file once, in full, before editing it. Do not re-read a file you")
    lines.append("  have already loaded this session.")
    if m["verify_cmd"]:
        lines.append(f"- Verify with `{m['verify_cmd']}`. Run it once when you are done, not")
        lines.append("  repeatedly.")
    lines.append("- Keep edits minimal and match the existing style.")
    lines.append("")
    return "\n".join(lines)
