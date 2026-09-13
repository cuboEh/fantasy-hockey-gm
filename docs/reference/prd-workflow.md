# PRD development workflow

Adapted from Beerio's `.claude/CLAUDE.md`, `refine-prd.md` and `prd.md` on
September 12, 2026. Repository instructions live in `AGENTS.md`; these procedures
can be requested in ordinary language, without a separate agent runner.

## Structure and lifecycle

Keep one active versioned PRD, currently [PRD 1.0](../PRD-1.0.md). The
[product plan](../product-plan.md) holds background and future scope. Existing research
reports remain evidence, not implementation backlogs. PRD versions are independent
of Python package versions. Archive a superseded PRD when its replacement becomes
active. Keep the documentation index, active PRD and product plan at the `docs/`
root. Put usage instructions in `guides/`, technical and workflow material in
`reference/`, and dated reports or superseded plans in `archive/`. Update the
documentation index and inbound links when moving or adding a document.

Use PRD > phases > functional requirements. Each phase has a short what/why
context and a table: FR | Requirement | Status | Notes. IDs use `P1-FR1`.
Requirements describe one observable behavior, without prescribing files or
implementation patterns. Put implementation pointers and verification in Notes.
Statuses are TODO, WIP, BLOCKED and Done. BLOCKED names the missing input or
dependency; it does not satisfy release acceptance. Existing code starts unverified
under a new contract, not presumed missing or complete.

## Refine the PRD

Example request: "Refine PRD 1.0 against the current draft tool."

1. Check numbering, phase dependencies, scope summary and atomic requirements.
2. For each requirement, identify an input/action and observable expected result.
   Resolve ambiguous terms, missing-data behavior and conflicting requirements.
3. Inspect relevant existing functionality and tests. Record reuse opportunities
   and the actual gap. Code presence alone is not acceptance evidence.
4. Apply routine wording corrections within the user's stated intent. Report
   material unresolved product choices without inventing their answers.
5. Report Ready, Needs revision or Blocked with concrete reasons. One refinement
   pass is normally enough; do not create a perpetual review loop.

## Implement and verify

Example request: "Implement P1 of PRD 1.0 and verify its acceptance checks."

1. State the FR IDs, user decision, supporting input and acceptance check.
2. Inspect and exercise existing behavior. Implement only the gap. A verified
   existing feature may satisfy an FR without a code change.
3. Prefer the smallest complete change through the existing guide and dashboard.
   Add a script only when existing entry points cannot reasonably support the task.
4. Verify the changed behavior at the appropriate layer. Run the required unittest
   suite for scoring changes. UI acceptance requires observing the local dashboard;
   backend tests alone do not certify UI behavior. Use the authorized local browser
   tools in isolated practice sessions and record actual observations. Yahoo browser
   automation remains prohibited.
5. Fix failures within the increment. After checks pass, repeat only when changes
   or unresolved evidence justify it. Record unrelated findings in the product plan.
6. Update FR status and Notes with the check, result and evidence location. Keep
   private snapshots and detailed player reports in ignored locations.
7. Report the user-visible result, verification and remaining limitations. Completing
   a phase does not authorize publishing, pushing or changing the live draft session.

## Compute and evidence discipline

Before a broader simulation, write down the decision it can change, baseline,
input snapshot, comparison metric, bounded cases/run budget and stopping rule.
Reuse existing saved drafts where possible. A run ends when its named question is
answered or its budget is exhausted; inconclusive evidence stays inconclusive.
Do not extend a run merely to find a favorable result.

Model-generated points establish a projected benefit only. A predictive advantage
requires sufficiently complete independent outcomes and fair baselines. Do not
tune on the acceptance fixtures or repeatedly inspected historical seasons and
then describe them as independent validation.

Beerio's phase/FR structure and evidence-backed status tracking are retained.
Its Ralph launch loop, production issue sync, automatic push, unconditional retests
and automatic expansion to all discovered bugs are not part of this workflow.

Codex's repository instruction mechanism is documented in the
[official AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
