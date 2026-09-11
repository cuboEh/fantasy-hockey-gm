# Repository map and consolidation audit

September 11, 2026. The original layout mixed a product, maintenance commands,
repeatable experiments, and dated pilot scripts in one active-looking workspace.
Not every Python file was unnecessary, but the presentation implied that every
script was part of preparing for the draft. That was misleading.

## What changed

| Area | Before | After | Decision |
| --- | ---: | ---: | --- |
| Installed Python package | 29 files | 27 files | Market comparison consolidated into `market.py`; two research-only helpers moved out. |
| Active `tools/` | 25 scripts | 8 scripts | Keep preparation and maintenance only. |
| `research/` | 0 files | 13 files | Eleven repeatable study runners plus two research-only helpers. |
| Owner archive | 0 scripts | 5 scripts | Preserve completed one-off studies and pilots. |
| `tests/` | 20 files | 20 files | Keep all 122 tests, including historical-method checks. |

Total Python file count fell from 74 to 73. The larger improvement is the active
surface shrinking, not pretending that relocating files deletes complexity.
Different source formats and different experiment schemas were not merged into
one oversized script. No source datasets, old results or draft databases were
removed. No Git history was rewritten.

The Yahoo comparison now uses `uv run fantasy compare-market` and the existing
`fantasy_hockey.market` module. The old standalone
`tools.compare_yahoo_market` entry point is retired, with no compatibility shim
left behind. Tracked commands and test imports were updated. The main README now
shows current use; its previous progress notes are preserved under the owner archive.

## Installed package responsibilities

These remain inside `src/fantasy_hockey/` because they implement current commands
or shared behavior those commands call:

| Modules | Why retained |
| --- | --- |
| `config`, `scoring`, `projections`, `board` | League settings, point arithmetic and forecast inputs. |
| `market` | Dated market data and the consolidated Yahoo comparison. |
| `draft`, `draft_cli` | SQLite pick tracking, legal roster assignment and recovery. |
| `preparation`, `preparation_cli` | Board preparation and draft-guide presentation. |
| `context_scenarios`, `workload_review` | Existing conditional cases and allocation validation. |
| `goalie_rates`, `goalie_coverage`, `goalie_weeks`, `goalie_weeks_cli` | Rate separation and current goalie-analysis commands. |
| `providers/nhl_schedule` | Distinct PDF and public-JSON schedule adapters with shared validation. |
| `draft_value`, `draft_planner`, `draft_completion`, `decision_cli` | Existing optional `draft-plan`; experimental, retained to avoid removing a working command. |
| `backtest`, `seasonlab` | Historical utilities also imported by current coverage/opportunity code. They cannot be archived safely just because of their names. |
| `history`, `replay` | Historical normalization and reusable lineup/replay primitives; retained with tests, not everyday commands. |
| `cli`, package initializers | Installed command entry and packaging. |

Pure historical analogue and case-catalog helpers now live in `research/`.
The installed package has no imports from `tools`, `research` or `archive`.
Research runners import the product's reusable functions, not the reverse.

## Active maintenance tools

See [tools/README.md](../tools/README.md) for the eight commands and their purpose.
Examples of apparent duplication that was deliberately retained:

- Schedule PDF import and JSON retrieval consume different sources. They share
  provider validation but are useful alternatives, not duplicate implementations.
- Tracker rehearsal checks persistence and recovery. Experimental planner
  rehearsal evaluates a more expensive workflow and moved into research.
- Goalie workload validation checks evidence and budgets; starter-rate building
  calculates rates from game data. They solve different problems.

## Research and archive

[Research index](../research/README.md) groups repeatable studies by purpose.
[Archived scripts](../archive/tg/personal/experiments/README.md) hold the first-study
correction, the four-case pilot builder, the historical CSG importer, the original
workload sensitivity report and the hard-coded starter-rate diagnostic.

The [migration manifest](../archive/tg/personal/experiments/migration.json) records
old paths, new paths and pre-move hashes. Existing scientific manifests retain
original paths and hashes. For exact prior code, use Git history at `cd35e90`;
current source fingerprints differ after this maintenance refactor. Old handwritten
commands outside tracked documentation need their module paths updated using the
manifest. Most archived tools preserve outputs, so reproductions need fresh paths;
the dated starter-rate diagnostic intentionally has hard-coded paths and no help CLI.

## Verification

All 122 unit tests pass. The consolidated market command regenerated a separate
private output and every one of its 390 rows, including baseline/scenario values,
matched the pre-refactor output exactly. Maintenance/research argparse entry points
received help-only smoke checks, with no network requests or expensive simulations.
The no-help dated diagnostic was not executed. The product-to-developer-script
import boundary was checked as well.

## Working rule from here

Start with `fantasy` for user-facing work. Add a new module only for a distinct,
reusable responsibility; put experiment orchestration in `research/`. Archive
completed one-off scripts with their rationale. Before running more studies,
identify the specific draft or roster decision the result could change.

The next product work remains the Yahoo comparison's high-impact projection gaps,
team conflicts and draft-session preparation, then weekly usable-game/streaming
advice. File cleanup is complete for this pass; it is not a reason to redesign the
application or rerun all historical experiments.
