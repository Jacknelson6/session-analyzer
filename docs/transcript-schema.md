# Claude Code transcript schema

What the parser relies on. Verified against real transcripts on a live install
(Claude Code 2.x). Treated as best-effort: the parser guards every field and
ignores unknown event types, so schema drift degrades gracefully.

## Location

```
~/.claude/projects/<path-encoded-cwd>/<session-uuid>.jsonl
```

- One directory per project. The cwd path is encoded by replacing `/` with `-`,
  e.g. `/home/user/Repo` → `-home-user-Repo`.
- One `.jsonl` file per session. One JSON object per line.
- Override the root with `CLAUDE_CONFIG_DIR` (the parser honors it).

## Line types

`type` is one of `user`, `assistant`, `attachment`, `queue-operation`,
`last-prompt`, plus occasional system/summary events. We read `user` and
`assistant`; the rest are skipped.

### Common top-level fields

`timestamp`, `sessionId`, `cwd`, `gitBranch`, `permissionMode`, `version`,
`isSidechain`, `parentUuid`, `userType`, `entrypoint`.

### assistant lines

```jsonc
{
  "type": "assistant",
  "timestamp": "2026-06-19T10:00:00.000Z",
  "gitBranch": "main",
  "message": {
    "role": "assistant",
    "content": [
      { "type": "thinking", "thinking": "..." },
      { "type": "text", "text": "..." },
      { "type": "tool_use", "name": "Read", "input": { "file_path": "..." } }
    ],
    "usage": {
      "input_tokens": 13720,              // billed at full input rate (cache miss)
      "output_tokens": 3570,
      "cache_read_input_tokens": 0,       // billed at the cheap cache rate
      "cache_creation_input_tokens": 25623
    }
  }
}
```

The `usage` block is the backbone of the token intent: cache-hit ratio is
`cache_read / (input + cache_read + cache_creation)`, and the `input_tokens`
portion is exactly what better prefix-caching would move to the cheap rate.

### user lines (tool results)

```jsonc
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      { "type": "tool_result", "is_error": false, "content": "..." }
    ]
  }
}
```

`is_error` drives the denial/error-rate signal; the length of `content` drives
the oversized-output signal.

### Compaction

Surfaced in some versions as an event with `subtype: "compact_boundary"` or an
`isCompactSummary` marker. Counted toward the context-thrash signal.
