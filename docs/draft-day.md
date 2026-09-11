# MVP 1 draft companion

Updated September 11, 2026. The September 13 draft has a prepared working board
and an empty 14-team snake-draft session. Tristan's actual slot and start time
remain unknown. Never set the rehearsal slot in the live session.

## Browser dashboard

Double-click **Fantasy Hockey Dashboard** on your Windows desktop, or open
[http://127.0.0.1:8765/](http://127.0.0.1:8765/) while the server is running.
The desktop launcher starts the local server in a minimized window. Keep it running
through the draft. Closing a browser tab does not delete progress.

When your team is on the clock, **Compare my next two picks** adds a roster-aware
comparison above the season-points board. It models daily lineup opportunity and
several possible opponent orders, with a separate same-pair stress comparison.
It is experimental; see [method, results and limitations](pick-comparison.md).
Results disappear after the draft state changes. The desktop launcher includes
the schedule required for this feature.

Use **My draft slot** to set the actual slot. **Record** opens a confirmation showing
the player, current pick and receiving team. Record every team's picks in order,
then inspect the refreshed recommendations and your roster. **Undo last pick**
reverses only the latest entry. Search includes restricted players so opponents'
picks can still be recorded. **Why / risks** explains the projection and relevant
review notes. **Download backup** saves a consistent SQLite copy that can be used
with the tracker or dashboard later. It includes all picks made before download.

The dashboard shares `var/draft-mvp1-2026-09-11.sqlite` with the CLI. Stale tabs are
prevented from applying actions to a changed draft state. Pages refresh every 15
seconds while visible; a Refresh button is also available. It is loopback-only and
uses no external website access or Yahoo automation.

For another machine or a backup session:

```sh
uv run fantasy dashboard --db PATH_TO_SESSION.sqlite --open
```

The Windows launcher installed for this checkout is at
`/mnt/c/Users/tgiac/OneDrive/Desktop/Fantasy Hockey Dashboard.cmd`. It selects the
Ubuntu-24.04 WSL distribution and this checkout's virtual environment. If either
is moved, update that local launcher. No desktop launcher or private data is
published in Git.

Dashboard validation: 133 tests pass. Browser checks used a separate practice
session for slot selection, filtering, pick entry and undo. HTTP tests cover
persistence, stale revisions, rejected foreign mutations and usable SQLite backup.
The live database was confirmed byte-identical to its original empty snapshot.

## Working files

- `var/mvp1-2026-09-11-final/board.json`: frozen working board, 513 identities.
- `var/mvp1-2026-09-11-final/board.csv`: offline spreadsheet fallback.
- `var/draft-mvp1-2026-09-11.sqlite`: live manual tracker, initially empty, slot unset.
- `var/mvp1-2026-09-11-final/initial-session.sqlite`: closed-database backup of that initial state.
- `var/mvp1-2026-09-11-final/manifest.json`: input, source-code and artifact hashes.
- `var/mvp1-rehearsal-2026-09-11-v2/`: practice results, separate from the live session.

All are local private files, ignored by Git. The old `var/draft-14-reviewed.sqlite`,
September 10 boards and prospective forecasts remain preserved.

## What determines the shortlist

The working forecast uses complete preseason stat totals from the author's
[free DtZ workbook](https://docs.google.com/spreadsheets/d/1hlwGkHQiC9PNg1bs5jHRK-pgyaI9QMbVRe0pMhOVuqU/edit),
received September 11. The public XLSX export is read locally without executing
formulas, scripts or account connections. This is a third-party projection source,
not an official NHL API. Its ranks, fantasy scores, ADP and eligibility are not
imported. Every fantasy total is recomputed using this league's scoring weights.

Use a single transparent working forecast rather than an unvalidated blend. The
historical baseline remains beside it for comparison. Existing injury/role and
goalie-start cases remain conditional alternatives; they do not apply a second
injury penalty or overwrite the provider forecast. There is no demonstrated
predictive edge from adopting this source.

The import accepted 490 complete projections across the wider registry. The
recommended pool is 373 players with both a complete projection and supplied
Yahoo eligibility. All supplied ADPs at or below 100 have coverage. The remaining
140 players stay searchable and can be recorded as actual picks, but are excluded
from automatic shortlists. Seventeen of those are in the supplied Yahoo list.
Missing estimates are never zeroes.

Identity checks exposed 48 conflicting provider IDs. Exact unique normalized name,
player type and team matches to the reconciled NHL registry correct those joins;
raw source IDs and corrections are preserved in `projection-import.json`.
Ambiguous identities, name variants without a reviewed alias and stale-team
projections are restricted. This fixes identity linkage, not projection accuracy.

Evangelista's current team is NJD, confirmed by the
[Devils release](https://frontend.d3.nhle.com/devils/news/evangelista-acquired-from-predators-release-9-1-26).
Tolvanen's is NYR, confirmed by the
[Rangers release](https://www.nhl.com/rangers/news/topic/features/rangers-agree-to-terms-with-eeli-tolvanen).
Their old-team DtZ forecasts remain restricted. Kane and Mantha also have provider
team discrepancies. Murashov remains an explicit watchlist player without a complete
forecast. The full restricted list is in `valuation-review.json`.

Yahoo data comes solely from Tristan's supplied 2026-27 snapshot: 390 identities,
264 ADPs, rank, preseason ADP, drafted percentage, positions and status. Missing
Yahoo ADP clears the old ESPN proxy instead of silently mixing series. Low drafted
percentages weaken interpretation of ADP; ADP is not a probability of availability.

The guide sorts supported, legally fitting players by working season points. It
shows projected appearances, rate, historical comparison, positional tiers, active
depth surplus, roster needs, later-ADP alternatives and risks. There is no forced
early-goalie rule. The first goalie is 64th by unadjusted season FP in this pool;
that is not a recommendation to wait until pick 64. Positional opportunity cost,
market depletion and the weekly appearance minimum still matter.

This MVP does not yet optimize the entire draft or convert season totals into
expected usable lineup points. Descriptive depth comparisons exclude bench demand
and overlap multi-position pools. Keep that limitation in mind when comparing
positions. The source forecast already includes workload assumptions; review health
and deployment before committing to a pick.

## Draft-day commands

Run from `/home/tgiacobbo/Code/fantasy-hockey-gm`:

```sh
uv run fantasy draft-guide --db var/draft-mvp1-2026-09-11.sqlite --limit 8
uv run fantasy draft board --db var/draft-mvp1-2026-09-11.sqlite --position D
uv run fantasy draft board --db var/draft-mvp1-2026-09-11.sqlite --search "McDavid" --json
```

When the actual slot is known, run `fantasy draft set-slot` with the same `--db`
and the actual slot number as its positional argument. Do not substitute a guessed
slot. Before it is set, the guide shows a general board without your roster needs.

Record every team's picks in order. Use the player actually selected, not the
example below. Matching by exact NHL ID or full name is safest.

```sh
uv run fantasy draft pick --db var/draft-mvp1-2026-09-11.sqlite "Connor McDavid"
uv run fantasy draft-guide --db var/draft-mvp1-2026-09-11.sqlite --limit 8
uv run fantasy draft undo --db var/draft-mvp1-2026-09-11.sqlite
uv run fantasy draft export --db var/draft-mvp1-2026-09-11.sqlite --output var/draft-progress.json
```

Undo removes the latest pick only. To correct an earlier pick, undo subsequent
picks and re-enter them in order. The tracker records observed choices even if
an opponent's roster is illegal, while the guide recommends fitting candidates.
Picks persist when the terminal closes. Changes are local bookkeeping, not Yahoo
roster actions.

For more goalie context, append
`--goalie-workloads private/goalie-workload-review-2026-09-10-v2.json` to `draft-guide`.
These are analyst start scenarios with dated role evidence, distinct from the
working forecast. Two goalies do not guarantee three active appearances weekly.
Relief appearances can count toward Yahoo's minimum; starter-only scenarios do
not capture all relief appearances. Recheck the September 12 review dates.

Verified Yahoo eligibility can be corrected with `fantasy draft positions --db ...
"Player Name" --eligible C,LW --note "Verified in Yahoo on YYYY-MM-DD"`.
Use `draft add-player --help` for a genuinely missing player. A watchlist pick
remains recordable without inventing its projection.

## Fallback and recovery

Open `board.csv` and filter `recommendation_restrictions` to blank for the supported
pool. Track taken players manually and respect C2/LW2/RW2/D4/G2/BN4. The file shows
working points, historical comparison, market columns, source notes and scenario
alternatives. Its overall rank includes the wider registry; it is not an ADP or
an optimal-pick rank. The static spreadsheet cannot recompute lineup fit after picks.

Between commands, when no tracker process is running, copy the SQLite file to a
new backup filename. To recover, use `--db` with that backup, check the last pick,
and re-enter any later picks. Do not replace the active file blindly. The initial
backup contains no picks; use recent backups during the draft. JSON exports retain
players, picks and audit events for inspection; automated JSON restoration is not
implemented.

## Verification and next actions

131 tests pass. The exact frozen board completed three lightweight 224-pick snake
scenarios. One persisted practice session checked all 16 guide turns, legal and
available candidates, undo/re-entry, full-roster completion, database-copy recovery
and export. Maximum guide latency was 0.144 seconds and pick entry 0.275 seconds
on this machine. These are workflow checks, not season simulations or evidence
of better draft outcomes. They caught and fixed string-versus-number ADP comparisons
after SQLite reloads.

Remaining pre-draft actions: set the actual slot, confirm start time/timezone,
refresh material health/role/eligibility news, and inspect the restricted watchlist.
If inputs materially change, prepare a new dated board and rehearse the changed
workflow without overwriting existing progress. Waiver timing and Yahoo API
approval are not prerequisites for this draft companion. Weekly lineup and
streaming work remains MVP 2; advanced opponent-strength ideas stay deferred.

## Reproduce from cached inputs

Choose a fresh output directory and database rather than overwriting these artifacts:

```sh
uv run fantasy prepare-draft \
  --board var/prepared-market-2026-09-10/board.json \
  --as-of 2026-09-11 \
  --dossier private/mvp1-2026-09-11/dossier.json \
  --market private/mvp1-2026-09-11/yahoo-adp.csv \
  --projection-workbook snapshots/2026-09-11/dtz/public-sheet.xlsx \
  --require-reviewed-projections --teams 14 \
  --output-dir var/mvp1-reproduction
uv run fantasy draft init --board var/mvp1-reproduction/board.json \
  --db var/mvp1-reproduction.sqlite --teams 14
```

The XLSX directory must contain `metadata.json` with season, receipt date and
SHA-256. Preparation verifies it. The dossier preserves the Yahoo snapshot and
team corrections; the import report records exclusions. `projection-comparison.csv`
decomposes differences from history into workload and rate components. No model
weights were tuned against these projections or the rehearsal results.
