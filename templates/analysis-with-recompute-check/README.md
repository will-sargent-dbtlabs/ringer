# analysis-with-recompute-check

For analysis/consulting work where a worker must **author** an analysis (not just recompute a known
number). The worker writes a deterministic `analysis.py` that emits `result.json` plus a human
`findings.md`; the check **re-runs the script** and runs an **invariant validator** you supply. This
verifies the analysis is reproducible and internally consistent — the analysis analogue of "the build
passes," instead of "a file exists."

## When to use
- A discrete analytical question against raw data ("what fraction of X", "how many Y by Z"), where you
  want the result reproducible and the interpretation traceable to computed values.
- Chain several of these for a multi-step investigation (see `data-investigation`).

## How it works
1. Worker writes `analysis.py` (reads named sources → writes `result.json`) + `findings.md`.
2. The check re-runs `python3 analysis.py` (catches hardcoded/non-reproducible results) then runs your
   `{{ASSERT_SCRIPT}}` against `result.json` to assert invariants (totals reconcile, ranges sane,
   required keys present). The validator must **print why it fails** — `diff`/explicit asserts, never
   `test -f`.

## Fill in
- `{{ANALYSIS_QUESTION}}`, `{{SOURCE_FILES}}`, `{{RESULT_KEYS}}` — the question, read-only inputs, and
  the result schema.
- `{{ASSERT_SCRIPT}}` — a small validator you write: load `result.json`, assert the invariants that
  make the answer *correct* (e.g. `success + reused + error == total`, `0 <= pct <= 100`), print the
  failing assertion. This is the product — keep it strict on substance.
- `{{ENGINE}}` — `codex` (default) or `claude-pty` (Sonnet; set `"full_access": true`).

## Notes
- Run the same question on two engines to cross-check an interpretation-sensitive result.
- Org engine policy: **codex** + **claude-pty** only (see `docs/MODEL-NOTES.md`).
