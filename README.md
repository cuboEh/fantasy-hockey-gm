# Fantasy Hockey GM

A local, private fantasy hockey draft and roster assistant for Tristan's Yahoo
league. The goal is expected fantasy production from usable roster slots, under
the league's scoring and constraints. Python and SQLite are sufficient.

## Current goal and milestones

The [product plan](docs/product-plan.md) is the current roadmap. MVP 1 is a dependable
September 13 draft companion: a reviewed league-specific board, Yahoo market
comparison, fitting shortlists and manual tracking. MVP 2 returns to weekly usable
games, lineup and streaming advice. A measurable edge is the objective, not an
established result. Deeper search stays parked while these deliverables are finished.

Deferred idea recorded in the [product plan](docs/product-plan.md): opponent
strength, repeated matchups and playoff schedule opportunity. This does not change
the current MVP 1 priority.

## Open the dashboard

Open [the local dashboard](http://127.0.0.1:8765/) while it is running, or double-click
**Fantasy Hockey Dashboard** on Tristan's Windows desktop to start it again.
Set your slot, browse recommendations, search/filter players, record every team's
picks, undo the last pick and download a SQLite backup. It shares the existing
live draft session. All changes are local, not Yahoo actions.

The dashboard also has an experimental **Pick now or wait?** comparison when you
are on the clock. It considers incremental daily lineup value, later options and
conditional downside. See [model and diagnostic results](docs/pick-comparison.md).

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

- [Yahoo comparison board](docs/yahoo-market-comparison.md): 390 players, ADP,
  eligibility, historical values and reviewed scenarios. Includes the full command.
- [Draft-day guide](docs/draft-day.md): manual pick tracking and recovery.
- [Strategy review](docs/strategy-research-2026-09-11.md): what we should test before
  changing recommendations.
- [Repository map](docs/repository-map.md): where the useful code lives, why it is
  retained, and how old script paths changed.

Current limitations: 52 Yahoo-table players lack baseline production estimates,
two team conflicts need review, and the actual draft slot is still unknown.
No optimizer has demonstrated a reliable competitive advantage. The two-turn and
completed-roster planners remain explicitly experimental.

## Project layout

```text
src/fantasy_hockey/              Installed CLI and reusable scoring/roster modules
tools/                          Eight data-preparation and maintenance commands
research/                       Repeatable studies and research-only helpers
tests/                          Tests for active and retained research behavior
docs/                           Current guides and research findings
archive/tg/personal/             Completed one-off scripts and old progress notes
snapshots/                      Private dated source data, ignored by Git
var/                            Private results and draft databases, ignored by Git
```

MVP 1 now has a frozen working board and a rehearsed manual session: 373 supported
Yahoo-eligible projections, 264 ADPs and an explicit restricted watchlist. See the
[draft-day guide](docs/draft-day.md) for current files, limitations and recovery.
Next: set your actual slot when known, confirm start time, and refresh material
news before September 13. Weekly usable-game and streaming advice follows as MVP 2. More elaborate
search is parked until evidence justifies it. Run checks with:

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
