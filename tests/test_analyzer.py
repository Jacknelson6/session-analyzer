"""Zero-dependency test suite (stdlib unittest).

Run: ``python3 -m unittest discover -s tests`` or ``python3 tests/test_analyzer.py``.
Covers transcript parsing, token-waste detection, repo-scan precision (the
false-positive classes we fought in Phase 1), rendering, and the budget ledger.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.budget import Budget, cap_for_mode
from src.config import is_test_file, is_vendored_for_findings, looks_generated, looks_minified
from src.extract import build_token_report
from src.render import render_markdown, render_terminal
from src.report import token_bundle
from src.repo_scan import _is_referenced, _norm_import, scan_repo
from src.sessions import load_sessions, parse_session
from src.theme import make_style, visible_len


def _write(tmp: Path, rel: str, content: str) -> Path:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


class TranscriptParsing(unittest.TestCase):
    def test_usage_and_tools_parsed(self):
        tmp = Path(tempfile.mkdtemp())
        events = [
            {"type": "assistant", "timestamp": "t1", "cwd": "/r", "gitBranch": "main",
             "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/r/a.ts"}}],
                         "usage": {"input_tokens": 100, "output_tokens": 20,
                                   "cache_read_input_tokens": 900, "cache_creation_input_tokens": 0}}},
            {"type": "user", "timestamp": "t2",
             "message": {"content": [{"type": "tool_result", "is_error": True, "content": "boom"}]}},
        ]
        f = tmp / "s.jsonl"
        f.write_text("\n".join(json.dumps(e) for e in events))
        s = parse_session(f)
        self.assertEqual(len(s.turns), 2)
        a = s.assistant_turns[0]
        self.assertEqual(a.input_tokens, 100)
        self.assertEqual(a.cache_read_tokens, 900)
        self.assertEqual(a.tool_calls, ["Read"])
        self.assertEqual(s.turns[1].tool_errors, 1)

    def test_malformed_lines_ignored(self):
        tmp = Path(tempfile.mkdtemp())
        f = tmp / "s.jsonl"
        f.write_text('not json\n{"type":"assistant","message":{"content":[],"usage":{"input_tokens":5}}}\n\n')
        s = parse_session(f)
        self.assertEqual(len(s.turns), 1)


class TokenWaste(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sys.argv = ["x"]
        # build a cache-waster session
        proj = self.tmp / "-r"
        proj.mkdir(parents=True)
        events = []
        for _ in range(6):
            events.append({"type": "assistant", "timestamp": "t", "cwd": "/r",
                           "message": {"content": [{"type": "tool_use", "name": "Read",
                                                    "input": {"file_path": "/r/same.ts"}}],
                                       "usage": {"input_tokens": 30000, "output_tokens": 500,
                                                 "cache_read_input_tokens": 100,
                                                 "cache_creation_input_tokens": 0}}})
            events.append({"type": "user", "timestamp": "t",
                           "message": {"content": [{"type": "tool_result", "content": "x" * 1000}]}})
        (proj / "w.jsonl").write_text("\n".join(json.dumps(e) for e in events))

    def test_low_cache_and_reread_detected(self):
        sessions = load_sessions(projects_root=self.tmp)
        rep = build_token_report(sessions)
        m = rep.per_session[0]
        self.assertLess(m["cache_hit_ratio"], 0.55)
        self.assertIn("/r/same.ts", m["reread_files"])
        self.assertGreater(m["waste_score"], 20)

    def test_report_serializable(self):
        rep = build_token_report(load_sessions(projects_root=self.tmp))
        from dataclasses import asdict
        json.dumps(asdict(rep))  # must not raise


class RepoScanPrecision(unittest.TestCase):
    """Guards the exact false-positive classes fixed in Phase 1."""

    def _repo(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        # an imported component + a tiny importer under 200 bytes
        _write(tmp, "components/Button.tsx", "export const Button = () => null;\n" * 3)
        _write(tmp, "app/page.tsx", "import { Button } from '@/components/Button';\nexport default Button;\n")
        # a genuinely orphan library module
        _write(tmp, "lib/dead.ts", "export const dead = 1;\n" + "// padding\n" * 20)
        # a test file (must NOT be an orphan)
        _write(tmp, "tests/x.test.ts", "import { Button } from '@/components/Button';\n")
        # a script entrypoint with shebang
        _write(tmp, "scripts/run.ts", "#!/usr/bin/env tsx\nconsole.log('hi');\n")
        # a JSDoc-heavy file (must NOT be 'commented-out code')
        _write(tmp, "lib/util.ts", "/**\n" + " * doc\n" * 15 + " */\nexport const u = 1;\n")
        _write(tmp, "lib/util-user.ts", "import { u } from '@/lib/util';\nexport const v = u;\n")
        return tmp

    def test_small_importer_prevents_orphan_fp(self):
        rep = scan_repo(str(self._repo()))
        orphan_finding = [f for f in rep["findings"] if f["id"] == "orphan-modules"]
        locs = orphan_finding[0]["locations"] if orphan_finding else []
        self.assertFalse(any("Button" in l for l in locs), "imported Button wrongly flagged")

    def test_real_orphan_detected(self):
        rep = scan_repo(str(self._repo()))
        orphan_finding = [f for f in rep["findings"] if f["id"] == "orphan-modules"]
        locs = orphan_finding[0]["locations"] if orphan_finding else []
        self.assertTrue(any("dead.ts" in l for l in locs), "real orphan missed")

    def test_test_files_not_orphans(self):
        rep = scan_repo(str(self._repo()))
        for f in rep["findings"]:
            self.assertFalse(any(".test." in l for l in f.get("locations", [])))

    def test_jsdoc_not_dead_code(self):
        rep = scan_repo(str(self._repo()))
        cc = [f for f in rep["findings"] if f["id"] == "commented-out-code"]
        locs = cc[0]["locations"] if cc else []
        self.assertFalse(any("util.ts" in l and "util-user" not in l for l in locs))

    def test_orphan_skips_uncommitted_work(self):
        import subprocess
        tmp = Path(tempfile.mkdtemp())
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

        def git(*a):
            subprocess.run(["git", "-C", str(tmp), *a], check=True, capture_output=True, env=env)

        git("init", "-q")
        _write(tmp, "lib/orphan_widget.ts", "export const widget = 1;\n" * 30)
        git("add", "-A")
        git("commit", "-qm", "init")
        # committed + unreferenced => an orphan candidate
        orph = [f for f in scan_repo(str(tmp))["findings"] if f["id"] == "orphan-modules"]
        self.assertTrue(orph and any("orphan_widget" in l for l in orph[0]["locations"]),
                        "a clean unreferenced lib module should be flagged")
        # now edit it => active work, must NOT be flagged
        _write(tmp, "lib/orphan_widget.ts", "export const widget = 2;\n" * 30)
        orph2 = [f for f in scan_repo(str(tmp))["findings"] if f["id"] == "orphan-modules"]
        locs2 = orph2[0]["locations"] if orph2 else []
        self.assertFalse(any("orphan_widget" in l for l in locs2),
                         "uncommitted edits must not be called dead code")

    def test_near_duplicate_detection(self):
        tmp = Path(tempfile.mkdtemp())
        body = "\n".join(f"export function f{i}(a,b){{return a+b+{i};}}" for i in range(40))
        _write(tmp, "a.ts", "import {x} from './x';\n\n" + body + "\n")
        _write(tmp, "b.ts", "import {y} from './y';\n\n\n" + body.replace("\n", "\n\n") + "\n")
        rep = scan_repo(str(tmp))
        nd = [f for f in rep["findings"] if f["id"] == "near-duplicate-code"]
        exact = [f for f in rep["findings"] if f["id"] == "duplicate-code"]
        self.assertTrue(nd, "near-duplicate not detected")
        self.assertFalse(exact, "reformatted clone wrongly flagged as exact duplicate")

    def test_norm_import(self):
        self.assertEqual(_norm_import("@/components/Button"), "components/Button")
        self.assertEqual(_norm_import("./a/b.tsx"), "a/b")
        self.assertIsNone(_norm_import("react"))

    def test_is_referenced_suffix(self):
        idx = {"Button": {"components/ui/Button"}}
        self.assertTrue(_is_referenced("src/components/ui/Button.tsx", "Button", idx))
        self.assertFalse(_is_referenced("src/other/Button.tsx", "Button", {"Button": {"a/Button"}}))


class Classification(unittest.TestCase):
    def test_helpers(self):
        self.assertTrue(is_test_file("app/x.test.tsx"))
        self.assertTrue(is_test_file("tests/y.ts"))
        self.assertTrue(is_vendored_for_findings(".claude/skills/foo/scripts/a.mjs"))
        self.assertTrue(looks_generated("// @generated by tool\ncode"))
        self.assertTrue(looks_minified("a" * 5000))
        self.assertFalse(looks_minified("short\nlines\nhere"))


class Rendering(unittest.TestCase):
    def _bundle(self):
        return token_bundle(_fake_token_report())

    def test_terminal_renders_without_color(self):
        out = render_terminal(self._bundle(), make_style(force=False))
        self.assertNotIn("\x1b[", out)
        self.assertIn("Token efficiency", out)

    def test_terminal_color_has_escapes(self):
        out = render_terminal(self._bundle(), make_style(force=True))
        self.assertIn("\x1b[", out)

    def test_markdown_renders(self):
        md = render_markdown(self._bundle())
        self.assertIn("# Token efficiency", md)
        self.assertIn("| Metric | Value |", md)

    def test_visible_len_ignores_ansi(self):
        self.assertEqual(visible_len("\x1b[38;2;1;2;3mhi\x1b[0m"), 2)


class BudgetLedger(unittest.TestCase):
    def test_cap_for_mode(self):
        self.assertEqual(cap_for_mode("tokens"), 200_000)
        self.assertEqual(cap_for_mode("both"), 400_000)
        self.assertEqual(cap_for_mode("repo", 500), 500)

    def test_charge_and_cap(self):
        b = Budget(cap_tokens=100)
        self.assertTrue(b.charge(60, "a"))
        self.assertFalse(b.charge(60, "b"))  # would exceed
        self.assertEqual(b.remaining, 40)


class CiGate(unittest.TestCase):
    def test_fail_under(self):
        from src.cli import _gate
        class A: fail_under = "A"
        class C: fail_under = "C"
        class N: fail_under = None
        b = {"verdict": {"grade": "B"}}
        self.assertEqual(_gate(A(), b), 1)   # B < A -> fail
        self.assertEqual(_gate(C(), b), 0)   # B >= C -> pass
        self.assertEqual(_gate(N(), b), 0)   # no threshold -> pass


def _fake_token_report() -> dict:
    return {
        "sessions_analyzed": 2,
        "repos": ["/r"],
        "totals": {"input_tokens": 1000, "output_tokens": 200, "cache_read_tokens": 500,
                   "cache_creation_tokens": 0, "overall_cache_hit_ratio": 0.33,
                   "est_total_cost_usd": 1.5, "reclaimable_cache_usd": 0.4, "sessions": 2},
        "findings": [{"id": "x", "title": "Test finding", "severity": "high", "category": "tokens",
                      "evidence": "ev", "recommendation": "fix", "impact_usd": 0.4,
                      "locations": [], "effort": "small", "autofixable": False, "tags": []}],
        "worst_sessions": [{"session_id": "abc", "waste_score": 40.0, "est_cost_usd": 1.0,
                            "cache_hit_ratio": 0.3, "reread_files": {}, "repeated_cmds": {},
                            "big_outputs": 0, "tool_histogram": {}}],
        "per_session": [],
    }


if __name__ == "__main__":
    unittest.main(verbosity=2)
