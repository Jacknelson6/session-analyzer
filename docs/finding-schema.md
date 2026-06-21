# Finding schema

Every item in a report, whether emitted by the deterministic pass or by your
synthesis, is a Finding. Write `synthesis.json` as a JSON list of these.

```jsonc
{
  "id": "cache-hit-ratio",        // stable kebab-case id, unique per finding
  "title": "Prompt cache is underused",
  "severity": "high",             // high | medium | low | info
  "category": "tokens",           // tokens | repo | structure | ...
  "evidence": "Overall cache-hit ratio is 33% across 40 sessions.",
  "recommendation": "Pin a stable cacheable prefix; stop injecting volatile context mid-prompt.",
  "impact_usd": 12.40,            // reclaimable dollars, 0 if not money-quantified
  "locations": ["CLAUDE.md:1-20", "lib/foo.ts"],  // optional, files/anchors
  "effort": "small",              // trivial | small | medium | large | unknown
  "autofixable": false,           // can a gated script apply it safely?
  "tags": ["cache", "prompt"]
}
```

## Authoring guidance

- **Evidence must be specific and checkable.** A number, a path, a count. Never
  "the code could be cleaner".
- **Recommendation must be copy-pasteable.** Quote the exact CLAUDE.md line to
  add, the exact settings key, the exact command. The reader should not have to
  design the fix.
- **Severity reflects impact, not effort.** A high-dollar, low-effort win is
  `high` severity + `trivial` effort, the best kind.
- **Rank by impact / effort.** The renderer sorts by severity then impact; put
  the single biggest win first in your prose summary regardless.
- **`autofixable: true` means a script can apply it behind the verify gate**
  (delete a junk file, strip a commented-out block). Anything needing judgment
  (deleting a module, rewriting a prompt) is `false`.
