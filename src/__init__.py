"""Claude session-history analyzer.

A portable, dependency-free toolkit that turns Claude Code session transcripts
and a target repository into a ranked, cost-aware improvement plan.

The heavy lifting is deterministic (pure Python, zero LLM tokens); an agent only
reads the compact digests this package emits and writes back a synthesis, keeping
the whole workflow inside a hard token budget.
"""

__version__ = "0.1.0"
