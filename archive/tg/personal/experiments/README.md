# Completed one-off experiments

Preserved, not deleted. These are not part of everyday preparation:

- `audit_draft_study.py`: correction of the original historical study.
- `build_context_pilot.py`: construction of the specific four-case pilot.
- `import_csg_market.py`: import of the historical 2024 workbook.
- `review_workloads.py`: the initial plus/minus-ten-appearance sensitivity report.
- `validate_starter_rates.py`: the dated 2015-2026 rate diagnostic, with hard-coded
  historical input/output paths. It is not a general command and has no `--help`.

Run archived scripts from the repository root as
`uv run python -m archive.tg.personal.experiments.NAME` with their original
arguments, where applicable. Existing outputs may intentionally block reruns.
Unit tests still exercise retained helper behavior. Do not automatically replace
these dated methods with current models when reproducing old studies.

`migration.json` records old/new script locations and original hashes. Exact
pre-consolidation code remains in Git history at commit `cd35e90`. Source imports
and document links were updated for the new locations; historical result data and
manifests were preserved. The historical README is one directory above this file.
