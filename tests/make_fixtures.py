"""Generate synthetic Claude Code transcripts that match the real JSONL schema.

Only one real transcript exists on a fresh machine, so we synthesize a spread of
sessions exhibiting the exact pathologies the analyzer is meant to catch
(cache misses, re-read churn, oversized outputs, retry loops, compaction) plus
healthy control sessions. Schema mirrors verified real events.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

random.seed(7)

FILES = [
    "/home/user/acme-app/lib/api/client.ts",
    "/home/user/acme-app/app/api/chat/route.ts",
    "/home/user/acme-app/components/ui/Button.tsx",
    "/home/user/acme-app/CLAUDE.md",
    "/home/user/acme-app/lib/db/connect.ts",
]
CMDS = ["npm run build", "npx tsc --noEmit", "npm run lint", "git status", "npm run test:e2e"]


def _assistant(content, usage, ts):
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": "/home/user/acme-app",
        "gitBranch": "main",
        "sessionId": "x",
        "version": "2.0.0",
        "message": {"role": "assistant", "content": content, "usage": usage},
    }


def _user(content, ts):
    return {
        "type": "user",
        "timestamp": ts,
        "cwd": "/home/user/acme-app",
        "gitBranch": "main",
        "permissionMode": "default",
        "message": {"role": "user", "content": content},
    }


def _usage(inp, out, cread, cwrite):
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read_input_tokens": cread,
        "cache_creation_input_tokens": cwrite,
    }


def tool_use(name, **inp):
    return {"type": "tool_use", "id": "t" + str(random.randint(0, 9999)), "name": name, "input": inp}


def tool_result(text, is_error=False):
    return {"type": "tool_result", "tool_use_id": "t0", "is_error": is_error, "content": text}


def make_session(kind: str, path: Path) -> None:
    events = []
    t = "2026-06-19T10:00:00.000Z"
    if kind == "cache_waster":
        # Big fresh input every turn, almost no cache reads.
        for i in range(8):
            events.append(_assistant([tool_use("Read", file_path=FILES[i % len(FILES)])],
                                     _usage(28000, 1200, 500, 0), t))
            events.append(_user([tool_result("file contents " * 200)], t))
    elif kind == "reread_churn":
        for i in range(10):
            events.append(_assistant([tool_use("Read", file_path=FILES[0])],
                                     _usage(4000, 600, 30000, 0), t))
            events.append(_user([tool_result("x" * 1000)], t))
    elif kind == "big_output":
        for i in range(4):
            events.append(_assistant([tool_use("Bash", command="cat huge.log")],
                                     _usage(3000, 400, 40000, 0), t))
            events.append(_user([tool_result("L" * 90000)], t))
    elif kind == "retry_loop":
        for i in range(5):
            events.append(_assistant([tool_use("Bash", command="npm run build")],
                                     _usage(3500, 500, 30000, 0), t))
            events.append(_user([tool_result("error: type X", is_error=True)], t))
    elif kind == "compaction":
        for i in range(3):
            events.append(_assistant([tool_use("Grep", pattern="foo")],
                                     _usage(6000, 800, 20000, 5000), t))
            events.append(_user([tool_result("hits")], t))
            ev = _user([{"type": "text", "text": "[compacted]"}], t)
            ev["subtype"] = "compact_boundary"
            events.append(ev)
    else:  # healthy
        for i in range(6):
            events.append(_assistant([tool_use("Read", file_path=FILES[i % len(FILES)])],
                                     _usage(1200, 700, 48000, 0), t))
            events.append(_user([tool_result("ok")], t))
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def main(out_root: str) -> None:
    root = Path(out_root) / "-home-user-acme-app"
    root.mkdir(parents=True, exist_ok=True)
    kinds = ["cache_waster", "reread_churn", "big_output", "retry_loop", "compaction",
             "healthy", "healthy", "cache_waster"]
    for i, kind in enumerate(kinds):
        make_session(kind, root / f"fixture-{i:02d}-{kind}.jsonl")
    print(f"wrote {len(kinds)} fixtures to {root}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/projects")
