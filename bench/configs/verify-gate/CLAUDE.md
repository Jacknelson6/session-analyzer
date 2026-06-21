# Verify before you finish

This project has a verification suite that your change must pass. It covers edge
cases — empty input, out-of-range values, rounding — that the task description
does not spell out and that are easy to miss.

Before you respond that you are done with ANY code change:

1. Run it: `python3 .verify/check.py`
2. Every check must pass. If any fail, fix the code (never the checks) and re-run.

Do not finish until it is green.
