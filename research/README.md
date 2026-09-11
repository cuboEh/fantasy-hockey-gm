# Research, outside the everyday draft workflow

These experiments are retained to explain results and evaluate concrete proposals.
They are not a recommendation to rerun every study, and no experiment is promoted
merely because it exists. Run from the repository root with
`uv run python -m research.NAME --help` where the runner supports arguments.

| Files | Role |
| --- | --- |
| `fetch_history` | Acquire the historical inputs needed for replay studies. |
| `import_hockeyinsights_market` | Reproduce the older non-Yahoo rank proxy. |
| `analogues`, `test_historical_analogues`, `replay_analogue_drafts` | Historical analogue helpers, study and draft replay. The `test_` runner is an experiment, not a unit-test suite. |
| `context_cases`, `join_context_case_outcomes` | Validate dated case labels and join outcomes afterward. |
| `validate_draft_planning` | Compare frozen draft policies with subsequent outcomes. |
| `score_matchups`, `evaluate_all_play` | Different evaluations: assigned synthetic matchups versus every opponent each week. |
| `summarize_seasons`, `summarize_draft_comparison` | Summaries for different experiment schemas, not interchangeable calculators. |
| `rehearse_planner` | Full experimental planner rehearsal, separate from tracker recovery checks. |

Earlier commands beginning `tools.NAME` now use `research.NAME` for these runners.
Tracked imports and documentation were updated. Historical result manifests keep
original paths and hashes; they were not rewritten to look newly generated.
