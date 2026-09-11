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

## Use the current workflow

```bash
uv sync
uv run fantasy --help
uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite
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

Next: improve the comparison board's important gaps, prepare the actual draft,
then deliver weekly usable-game and streaming recommendations. More elaborate
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
