# Preparation and maintenance commands

Run these from the repository root with `uv run python -m tools.NAME --help`.
The normal product entry point is `uv run fantasy`; Yahoo comparison is now
`fantasy compare-market`, not a separate tools script.

| Script | Purpose |
| --- | --- |
| `fetch_open_data` | Retrieve the published Hockey Insights dataset. |
| `fetch_nhl_schedule` | Cache NHL website schedule JSON and validate it. |
| `import_nhl_schedule` | Alternative import from a downloaded NHL schedule PDF. |
| `build_goalie_rates` | Derive starter/relief estimates from cached game records. |
| `audit_goalie_workloads` | Validate reviewed goalie allocations and evidence. |
| `run_context_scenarios` | Evaluate an explicit context dossier. |
| `freeze_draft_forecasts` | Preserve a dated prospective forecast snapshot. |
| `rehearse_draft` | Verify draft tracking, backup and recovery in isolated sessions. |

JSON fetching and PDF import are different provider paths, not duplicate parsers.
Most commands preserve outputs by requiring new destination paths. Fetch commands
use network access when their documented caches are missing; they are not tests.
Research runners moved to `research/`. See the [repository map](../docs/reference/repository-map.md).
