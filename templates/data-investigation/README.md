# data-investigation

Sequential, read-only investigation of a live system or dataset (API pulls, log/artifact analysis,
"why is X happening") where **each step's question depends on the previous answer**. Each step is a
**one-task manifest** with an executed invariant check — so an exploratory investigation stays
visible, verified, and logged instead of drifting into inline hacking.

## When to use
- Consulting/diagnostic work: "why is CI over-building", "where is the spend", "is the pipeline
  stale" — the shape of the Nordstrom SAO engagement.
- You (orchestrator) frame each question and read each result; workers do the pulling and computing.
  The framing is yours; the typing and verification are delegated.

## How it works
- Run one step, read its `finding.json` + `finding.md` off the artifact page, decide the next
  question, run the next step (same `run_name` → one accumulating artifact). This is a **chain**, not a
  parallel swarm — the win is verification + cost, not parallelism.
- Each step's check asserts invariants on `finding.json` (counts reconcile, ranges sane, required
  evidence present) and prints why it fails. Verify content, never `test -f`.
- Steps that hit an API set `"full_access": true` and put the exact credential-loading + pull commands
  in the spec (workers are stateless — never make them discover the interface).

## Fill in
- `{{STEP_QUESTION}}`, `{{SOURCE_FILES_OR_ENDPOINTS}}`, `{{HOW_TO_RUN}}`, `{{FINDING_KEYS}}`,
  `{{ASSERT_SCRIPT}}`, `{{ENGINE}}`.

## Notes
- When a step produces a claim that will land in a deliverable, promote it to a `report-claim-audit`
  run so the number is independently reproduced before it ships.
- Org engine policy: **codex** + **claude-pty** only (see `docs/MODEL-NOTES.md`).
