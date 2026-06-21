# The loop / output-quality cap

How much can an encoded verification loop improve output quality, and where does
that improvement stop? This is the loop analog of the ~41-47% token ceiling.

## Method

A 4-tier difficulty ladder (T1 easy to T4 very-hard "symptom far from cause"
localization bugs), each task graded by a HIDDEN test the agent never sees (the
grader is added only after the agent process exits). Two arms on identical tasks:

- **Arm A (no gate):** implement the task, one shot.
- **Arm C (gate):** a blind verify gate that makes the agent write and run its
  own edge-case tests against the definition of done before finishing. It never
  sees the hidden grader.

Run on Sonnet 4.6 and Opus 4.8. Harness: `bench/run_ladder.py`.

## Results

**Over-specified ladder** (the README spelled out the edge cases): both models,
every tier, 100% first-pass in both arms. Gate lift 0.

**Under-specified ladder** (goal only, edges hidden in the grader): T1-T3 both
models still 100% first-pass (they infer the implicit edges). T4: Opus 100%;
Sonnet first cracks.

**T4 firmed** (8 localization tasks, n=3):

| model | Arm A first-pass | Arm C (gate) | rescued / broke | token cost |
| --- | --- | --- | --- | --- |
| Opus 4.8 | 100% (24/24) | 100% | 0 / 0 | +15% |
| Sonnet 4.6 | 92% (22/24) | 96% (23/24) | 2 / 1 (net +1) | +15% |

Sonnet one-shots 7 of 8 hard localization tasks; only one (billing proration)
genuinely stresses it (1/3 first-pass), and the gate only lifts it to 2/3, not
3/3. Opus one-shots all 8.

## The cap

First-pass correctness is already 92-100% for both frontier models even on
very-hard localization tasks. So:

- The verify-loop's **ceiling of improvement on well-formed coding tasks is
  single-digit percent**.
- It **costs ~15% more tokens**.
- At the hardest tasks it **churns**: it breaks about as often as it rescues.
- It does **not reliably fix localization failures** (a blind self-test loop
  cannot tell the model WHERE the bug is; even the one task Sonnet fails only
  goes 1/3 to 2/3).

The loop's value is bounded by the model's first-pass FAILURE rate. On a complete
spec that is ~0. The loop pays in a narrow band: requirements that are genuinely
implicit AND missable. In a separate edge-case suite where the trap was both
unstated and non-obvious, the same gate took Sonnet from 50-67% to 100%
(`bench/tasks-loop.jsonl`). That band is where the loop earns its tokens.

## Takeaway for the skill

Recommend verify-loops SURGICALLY, not as a blanket gate:

- Add them where past sessions show real first-pass failures or human
  corrections, which is exactly what session-analyzer detects from history.
- For hard localization bugs the loop needs an external localization signal: a
  failing regression suite, a different-model judge, or a human. A blind
  self-test loop alone hits the wall.
- A blanket gate on already-well-handled tasks is pure token overhead with churn
  risk.

## Honest limits

Small n (n=3 across 8 hard tasks); correctness graded by hidden tests only (no
judge-rubric quality score in this run); tasks are puzzle-to-module scale, not
full-repo; the SWE-bench Verified external-validity anchor was specified but not
run. The cap is located to a tier and a regime, not estimated to the point.
