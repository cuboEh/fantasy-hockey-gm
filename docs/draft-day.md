# Local draft board and tracker

The first real-player board uses a historical-rate baseline, not a final trained
forecast. Yahoo eligibility, current injury/role changes, uncertain workloads and
rookies need review. The tracker performs local manual bookkeeping only.

See [pre-draft readiness](pre-draft-readiness.md) for the latest reviewed board,
imports, rehearsal results and unresolved inputs.

## Current artifacts

- `var/prepared-market-2026-09-10/board.json`: current prepared board, contributions, source flags, review notes and market proxy.
- `var/prepared-market-2026-09-10/board-with-reviews.csv`: spreadsheet fallback, including unranked entries and review sources.
- `var/draft-14-reviewed.sqlite`: current 14-team session, initially empty with your slot unset. Older 12/13-team sessions are preserved.
- `var/baseline-diagnostic.json`: limited retrospective rate comparison, not a valid as-of backtest.

All of these are private and ignored by Git. The reviewed board has 461 historical
baseline estimates and nine unranked players without usable history. Source pool
coverage is incomplete. An unranked player is not a zero-value player.

## Reproduce the board

```sh
# A one-time download. Use a new dated directory for later refreshes.
uv run python tools/fetch_open_data.py snapshots/2026-09-10/hockeyinsights

uv run fantasy build-board --config config.local.toml \
  --input snapshots/2026-09-10/hockeyinsights/fantasy_2027.json \
  --moneypuck-dir snapshots/2026-09-10/moneypuck \
  --as-of 2026-09-10 --output var/draft-board.json --csv var/draft-board.csv
```

The existing snapshot need not be downloaded again. MoneyPuck annotation is
optional; omit its flag if those CSVs are not available locally. Input and config
hashes are retained. No MoneyPuck feature currently changes projected points.

Each scored stat is a 60%/30%/10% blend of historical per-appearance rates from
2025-26, 2024-25 and 2023-24, renormalized over available seasons. We recompute
your scoring from counts rather than using another site's fantasy scores.
Appearance estimates carry forward weighted historical GP, scaled from 82 to 84
and capped at 84. This deliberately transparent assumption needs role/injury
review, especially for goalies. It does not model team start-allocation constraints.

## Use the tracker

Run from the project directory. Use the current 14-team session.
Your slot can be set when known; the example slot below is illustrative.

```sh
uv run fantasy draft board --db var/draft-14-reviewed.sqlite
uv run fantasy draft set-slot --db var/draft-14-reviewed.sqlite 7
uv run fantasy draft board --db var/draft-14-reviewed.sqlite --position D --limit 15
uv run fantasy draft board --db var/draft-14-reviewed.sqlite --search "McDavid" --json
uv run fantasy draft pick --db var/draft-14-reviewed.sqlite "Connor McDavid"
uv run fantasy draft undo --db var/draft-14-reviewed.sqlite
uv run fantasy draft export --db var/draft-14-reviewed.sqlite --output var/draft-backup.json
```

Record every team's picks, in order. Team ownership is computed from snake order;
it is not inferred from player names. Matching by exact NHL ID or exact name is
preferred; ambiguous partial names fail. Picks survive closing the terminal.
Undo reverses only the latest pick and leaves an audit event. Fix an earlier
mistake by undoing subsequent picks and re-entering them in order.

The tracker records observed draft choices even if a roster no longer fits the
configured slots; it must reflect reality. The board reports unassigned players.
Candidate fit uses joint positional matching, supports multi-position eligibility,
and excludes injury slots from draft capacity. The displayed order is season
points among fitting players, not value over replacement or a next-pick optimizer.
Before your slot is known, fit is unset and the board is a general ranking.

## Correct provisional inputs

Primary NHL positions are not Yahoo eligibility. Record verified eligibility:

```sh
uv run fantasy draft positions --db var/draft-14-reviewed.sqlite "Player Name" \
  --eligible C,LW --note "Verified in Yahoo draft room on YYYY-MM-DD"
```

For pre-draft board rebuilds, an optional ignored overrides JSON is keyed by
`nhl:<id>` and can contain `projected_games`, `positions`, `team`, `source`, `note`
and `as_of`. Source, note and date are required. Pass `--overrides` to build-board.
This supports documented workload scenarios without silently changing history.
Injury information should come from dated reporting, not assumptions from games
missed alone. Existing draft sessions retain their imported board; rebuilding a
JSON board does not mutate an ongoing draft or its picks.

## Before relying on this during the draft

Confirm your draft slot. Check leading candidates' Yahoo eligibility and
current roles/injuries. Review the unranked rookie watchlist and source conflicts.
Compare a permitted independent projection export if available. Rehearse in a
separate database and keep the CSV and a database copy locally.

When creating a new session, use `draft init --board ... --db ... --teams ...`.
Initialization refuses to overwrite existing databases. JSON exports preserve
players, picks and audit events for inspection; automated restoration from those
exports is not implemented. A filesystem copy of the closed SQLite database
provides a directly usable backup.
