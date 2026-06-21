# Optimization log

Record of each tuning round against a real ~4,000-file production repo (31 MB)
and a synthetic transcript fixture set. Each round states the
problem, the change, and the measured effect. Goal: every finding the tool emits
should be true and actionable.

Baseline (v0):

- Repo mode: Grade D. 10 false-positive "orphans" (all test/spec files), 379
  "commented-out code" files (JSDoc plus vendored noise), generated and vendored
  files flagged as oversized.
- Tokens mode: Grade C on fixtures; all 5 pathologies detected.
- Runtime: 2.6s on the full repo.

## Phase 1: repo-scan precision

A false positive costs more than a miss. Ground truth each round was a grep over
the real repo.

1. Test/spec/config files excluded from orphans (runner entrypoints, not dead
   code).
2. Commented-out-code heuristic now matches only `//`/`#` code-ish lines and
   excludes JSDoc. 379 -> 21.
3. Generated/minified/vendored classification added in `config.py` (lockfiles,
   `.min.*`, `.d.ts`, `@generated`/`DO NOT EDIT` headers, long-line minified);
   excluded as finding targets.
4. Duplicate findings split into `duplicate-code` (medium) and `duplicate-docs`
   (low); "import a shared module" is wrong advice for Markdown.
5. Bug: files under 200 bytes were skipped entirely, so small importers
   (`loading.tsx`, barrels) never entered the reference index (~80 orphan FPs).
   The 200-byte floor now gates only duplicate-hashing, not the read.
6. Bug: generated/minified files were skipped before reference indexing,
   orphaning everything a dynamic-import registry lazy-loads. Reference indexing
   now runs before that exclusion.
7. Path-resolution orphan matching: an import must resolve to the file's
   extensionless path suffix, indexed by last segment. Verified 12/12 shown
   orphans had zero mentions in the repo.
8. Files with `#!` or named in `package.json` scripts/bin are entrypoints, not
   orphans.
9. Scripts spawned by bare name count as references. Removed 3 FPs.
10. Library vs script orphan tiering: split into `orphan-modules`
    (app/components/lib, medium) and `unreferenced-scripts` (info). Backfill
    scripts are not "dead code".
11. Vendored skill/plugin internals counted for size and references but never
    flagged. Grade D -> B; every remaining finding points at the repo's own code.

Result: repo mode went from Grade D (FP-dominated) to Grade B (100% of
spot-checked findings true) at ~1.5s on 4,059 files.

## Phase 2: token signal and output quality

12. Cache finding fires when the overall ratio is low OR >= $0.50 is
    reclaimable, and names the 3 worst sessions, so waste is not hidden behind
    healthy averages.
13. Empty state: zero sessions renders "no sessions found" with a discovery
    hint, not "Grade F, 0% cache".
14. Bug: `both` mode reported `min()` of the two grades (the better one); now
    surfaces the worse grade.
15-16, 28. Grammar fixes and a per-session cost sparkline under the KPIs.
17. Removed every em/en dash from code, docs, and output.
18. Cleared every unused import in the tool's own source (pyflakes).

## Phase 3: safety, breadth, workflow

19-21, 29. Committed-secret detection (later removed). A secret scanner was added
    and then cut: pasting keys is normal usage, not a finding this tool should make.
22. Removed a dead config threshold (`broad_search_hits_chars`).
23. `doctor` command prints discoverable projects/sessions.
24. `--format json` for CI and programmatic use.
26. Near-duplicate detection: hashes structure-only content (whitespace,
    imports, and comments stripped) so reformatted copy-paste still collides,
    without double-counting exact duplicates.
27. Markdown output polish: charts render as block-bars with values; the
    sparkline carries over.
30. `--since DAYS` recency filter.
31. `--fail-under GRADE` exit-code gate for CI/merge.

Final state: 19 tests green, pyflakes-clean, ~1.5s on the 4,059-file repo. Token
mode validated against a live session (98% cache, Grade A). Repo mode
trustworthy on a real ~4,000-file repo (Grade B) and on the tool's own source (Grade B).

## Self-improvement loop (dogfooding on real history)

The loop: run the analyzer on real session history and on this repo, read its
own output as the signal, fix the highest-leverage flaw it reveals, run the
tests, ship. Repeat. Each round below was triggered by something the tool got
wrong on a real run.

32. Removed committed-secret detection entirely. Pasting keys is normal usage,
    not a finding, and it was leading the verdict with noise.
33. `render` now auto-merges a sibling `synthesis.json` and re-sorts by severity
    (the agent previously hand-rolled a JSON merge). Added `--synthesis`.
34. Cache finding no longer reports HIGH "underused" when the overall ratio is
    healthy: a few bad outliers are now a LOW "concentrated in a few sessions".
    It had been contradicting a Grade A verdict and burying the real findings.
35. Orphan detection is git-aware: files with uncommitted changes are active
    work and are never flagged dead. Caught a real FP on an in-flight crypto.ts.
36. Added `bench/`: an A/B harness that runs the same tasks under `claude -p`
    with vs without a skill-recommended orientation `CLAUDE.md`, recording real
    token usage and a deterministic success check. First pilot (5 tasks, Sonnet
    4.6, x2 repeats): 50.9% fewer tokens, task success unchanged (100% in both
    arms). The savings claim is now measured and reproducible, not estimated.
37. Hardened the claim with two more rounds. Harder fixture tasks (multi-file
    edits, cross-file comprehension): 26.8% fewer tokens, quality held. A large
    real repo (navigation, its generic CLAUDE.md vs none): flat-to-negative
    (-11.6%), because grep already finds files in a turn or two and a generic doc
    is overhead, not a map. Honest headline revised from 51% (easy suite only) to
    ~41% blended across 8 tasks. Lesson: the win is in exploration/re-read-heavy
    work, not cheap navigation. Runner now stores the agent's answer text so a
    failed check is debuggable (one real-repo nav task failed both arms on a bad
    check assumption, invisible until now).
38. RSI loop cycle 1 (target >=70% tokens + >=90% first-pass): tested context
    isolation / fan-out (one fresh sub-session per feature) vs a monolithic
    session on a 5-feature task. Fan-out used +192% MORE tokens: per-session base
    overhead dominates on small tasks. Both arms hit 100% correctness behind the
    verify gate. REJECTED as a token lever at this scale. Takeaways: the
    orientation map (~47%) is the realistic token ceiling on benchmarkable tasks;
    fan-out only pays at much larger scale; the verify gate (not decomposition)
    drives first-pass correctness. Adopted looper as the loop-architecture
    baseline (docs/loop-architecture.md).
39. RSI loop toward the loop/output-quality cap. Built a 4-tier difficulty ladder
    (11 workflow-authored, self-validated fixtures) and ran Arm A (no gate) vs Arm
    C (blind verify gate) on Sonnet 4.6 and Opus 4.8. Cycle 1 result: BOTH models
    hit 100% first-pass on EVERY tier, so gate lift was 0 everywhere (the gate
    only added 15-45% tokens). Cause: the fixtures over-specified the edge cases in
    the README definition-of-done, so the model implemented them first-pass.
    Finding: the verify-loop's value is bounded by the model's first-pass FAILURE
    rate; on a complete spec that is ~0, and output quality is already at the
    ceiling. Cycle 2 under-specifies (goal only, edges hidden in the grader) to
    find the cap inside the loop's actual operating band.
