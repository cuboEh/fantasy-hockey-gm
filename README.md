# Fantasy Hockey GM

A local, private fantasy hockey draft and roster assistant for Tristan's Yahoo
league. The goal is expected fantasy production from usable roster slots, under
the league's scoring and constraints. Python and SQLite are sufficient.

## Current goal and milestones

PRD 2.0 is active as of September 14: a dependable daily and weekly GM assistant,
with explicit prediction-model development and research. The draft is complete.
The [GM workspace](docs/guides/gm-workspace.md) now supports complete supplied
league imports, dated statistical forecasts, lineup plans, gap explanations and
single pickup comparisons. It preserves research context and dated reviews across
refreshes. Launch an initialized workspace with `fantasy gm dashboard`.

The [active PRD](docs/PRD-2.0.md) records 30 verified requirements and one blocked
requirement: supported Yahoo reads. The
[daily/seven-day evaluation](docs/reference/gm-horizon-evaluation.md) compares the
baseline and unchanged recency candidate on 153,263 paired cases. The candidate
remains experimental; no independent predictive advantage is claimed.
Current real-league actions require verified assignments, availability and workload.

The [product plan](docs/product-plan.md) retains the broader roadmap, including
later selected-offer trade analysis and further model experiments. Existing draft
commands remain available for reference and isolated investigation.

## Earlier draft model work

The archived draft notes record clearing seven test picks with a backup and
initializing the draft session at pick 1. Seven priority players received dated
dashboard notes; see the [evidence refresh](docs/archive/priority-refresh-2026-09-11.md).
That refresh left numerical forecasts unchanged. NHL team diversification and stacking are
recorded as deferred ideas in the product plan.

The [validation report](docs/archive/validation-2026-09-11.md) records the historical replay,
fixed opponent-foresight and stale-player issues, forecast-error breakdown,
and final-roster goalie tradeoffs. All 147 tests pass. Historical outcome coverage
is still insufficient to claim an advantage. Next: refresh material draft-target
roles, then repair historical participation/eligibility before tuning weights.

## Open the dashboard

Open [the local dashboard](http://127.0.0.1:8765/) while it is running, or double-click
**Fantasy Hockey Dashboard** on Tristan's Windows desktop to start it again.
Set your slot, browse recommendations, search/filter players, record every team's
picks, undo the last pick and download a SQLite backup. It shares the existing
live draft session. All changes are local, not Yahoo actions.

The dashboard also has an experimental **Pick now or wait?** comparison when you
are on the clock. It considers incremental daily lineup value, later options and
conditional downside. See [model and diagnostic results](docs/guides/pick-comparison.md).

The dashboard uses Python's standard library and a single local HTML page, with
no new dependencies or external services. For another installation, start it with:

```sh
uv run fantasy dashboard --db var/draft-mvp1-2026-09-11.sqlite \
  --schedule var/schedule-20262027-2026-09-10.json --open
```

Keep its server running while using the page. The desktop launcher starts a
minimized server window and opens the browser. Reopening it reuses the same session.

## Use the current workflow

```bash
uv sync
uv run fantasy --help
uv run fantasy draft-guide --db var/draft-mvp1-2026-09-11.sqlite --limit 8
uv run fantasy compare-market --help
```

Local data paths require this checkout's private inputs. No credentials or private
downloads are included in Git.

- [Yahoo comparison board](docs/guides/yahoo-market-comparison.md): 390 players, ADP,
  eligibility, historical values and reviewed scenarios. Includes the full command.
- [Draft-day guide](docs/guides/draft-day.md): manual pick tracking and recovery.
- [Strategy review](docs/archive/strategy-research-2026-09-11.md): what we should test before
  changing recommendations.
- [Repository map](docs/reference/repository-map.md): where the useful code lives, why it is
  retained, and how old script paths changed.

Current limitations: 17 Yahoo entries remain restricted in the working projection
board, historical validation lacks complete observations, and the actual draft
slot is still unknown.
No optimizer has demonstrated a reliable competitive advantage. The two-turn and
completed-roster planners remain explicitly experimental.

## Project layout

See the [documentation index](docs/README.md) for guides, references and archived reports.

```text
src/fantasy_hockey/              Installed CLI and reusable scoring/roster modules
tools/                          Eight data-preparation and maintenance commands
research/                       Repeatable studies and research-only helpers
tests/                          Tests for active and retained research behavior
docs/                           Documentation index, active PRD and product plan
docs/guides/                    Draft-day usage and comparison instructions
docs/reference/                 Development, methods and source references
docs/archive/                   Dated studies and previous progress reports
archive/tg/personal/             Completed one-off scripts and old progress notes
snapshots/                      Private dated source data, ignored by Git
var/                            Private results and draft databases, ignored by Git
```

The draft release is retained for reference. Active development is the
[PRD 2.0 GM workspace](docs/guides/gm-workspace.md): supplied league imports,
dated forecast research, daily lineup plans and single pickup comparisons.
Current Yahoo inputs and connected reads still need verification. Run checks with:

```bash
uv run python -m unittest discover -s tests -v
```

## Yahoo access and data handling

Yahoo read-access application submitted September 10, 2026; approval pending.
Requested information is the user's authorized league settings, roster/eligibility,
availability/ownership, standings, matchups and transaction history where supported.
The intended user base is one individual using the tool privately in one league.
There is no deployed service or Yahoo connection.

Roster changes remain manual through Yahoo. No Yahoo write access, browser
workaround or scraping is implemented. Provider data is used subject to applicable
agreements and attribution requirements. Credentials, account information and
private snapshots are not committed or redistributed.

This independent project is not affiliated with Yahoo or the NHL. Earlier progress
notes are preserved in the [historical README](archive/tg/personal/README-before-consolidation.md).
