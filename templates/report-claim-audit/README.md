# report-claim-audit

Audit the headline figures in an analysis/report deliverable before it ships, by having
**two independent workers recompute the numbers from raw data** and verifying both against an
**authoritative recompute** the workers never see. This is the consulting/analysis analogue of a
test suite: the "test" is *does the claim reproduce from the raw data*, not *does the file exist*.

## When to use
- A report, memo, or dashboard makes quantitative claims and you want them provably backed by the raw
  data before a customer sees them.
- You want cross-model verification: two engines (e.g. `codex` + `claude-pty`/Sonnet) recompute
  independently; agreement with the truth is the signal, disagreement surfaces an interpretation error.

## How it works
1. You (orchestrator) write a **truth-recompute command** — a script that derives the canonical
   figures straight from the raw source files and prints them as JSON. This is the check's ground
   truth; keep it small and obviously correct.
2. Each worker independently recomputes the SAME figures from the named raw sources and writes
   `audit.json` with a fixed key schema. Workers do **not** see the truth command or each other.
3. The check (`checks/claim_audit_check.py`) runs the truth command and compares every audited key
   (floats within `--tol`), printing WHY on any mismatch. Exit 0 only if all match. Two workers both
   passing = independent agreement.

## Fill in
- `{{SOURCE_FILES}}` — absolute paths to the raw data (read-only).
- `{{FIGURE_SPEC}}` — plain-language definition of each figure and which source to compute it from.
- `{{OUTPUT_KEYS}}` — the exact JSON schema for `audit.json` (must match the truth command's keys).
- `{{TRUTH_CMD}}` — command that prints authoritative truth JSON (e.g. `python3 /abs/truth_recompute.py`).
- `{{CHECK_SCRIPT_PATH}}` — absolute path to `checks/claim_audit_check.py`.

## Notes
- Keep the audited figures to things recomputable from committed/raw files so the audit is reproducible.
- `claude-pty` (Sonnet) is a network worker (it calls Anthropic) → its task needs `"full_access": true`
  and `allow_full_access = true` in config. `codex` runs sandboxed.
- Engine policy for this org: worker lanes are **codex** and **claude-pty** only (see
  `docs/MODEL-NOTES.md` → Engine policy). Do not route through opencode/OpenRouter or grok.
