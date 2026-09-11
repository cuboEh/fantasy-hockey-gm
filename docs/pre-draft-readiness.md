# Pre-draft readiness, September 10, 2026

The preparation workflow is usable locally. The forecast still needs current
Yahoo eligibility, complete rookie projections and quantitative workload review.
The new default session is `var/draft-14-reviewed.sqlite`, empty with your slot
unset. Existing sessions and source boards are preserved.

## Completed in this pass

- Fixed consensus-only goalies being classified as skaters. Connor Ingram was
  affected; his missing projection remains explicit.
- Added an audit, dated review dossier, strict market import and complete-stat
  projection import. Unknown IDs, future evidence, mixed ranking series and
  incomplete scored stats fail rather than silently joining or filling zeros.
- Added three missing rookie identities and eight injury-review flags. The board
  has 470 players: 461 historical baseline estimates and nine unranked entries.
  This is a targeted first review, not a complete injury or rookie census.
- Imported 250 ESPN rank proxies from the already downloaded, permitted
  [Hockey Insights dataset](https://hockeyinsights.ca/opendata/). They are secondary
  published rankings, not Yahoo ranks or ADP. The snapshot is dated August 31.
  They change market context and rehearsal opponents, never projected points.
- Added a guide with roster needs, positional tiers, depth surplus, review notes
  and a ten-fewer-appearances sensitivity in JSON. These are descriptive metrics,
  not uncertainty intervals or calibrated next-pick probabilities.
- Rehearsed complete 14-team, 224-pick drafts with three preference seeds, both
  with a points proxy and with the imported market proxy. All teams filled active
  slots. SQLite persistence, completed-draft rejection, undo/re-entry and backup
  recovery passed. All 14 draft slots have opening-round scenarios.
- Added a way to record a missing player during the draft without losing picks.
- Kept usable-game choices as a separate shadow comparison. It uses the previous
  season's calendar as a congestion proxy and inspects 12 fitting candidates.
  It does not change the live board or claim to use the upcoming NHL schedule.

## Use now

```sh
uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite --limit 15
uv run fantasy draft board --db var/draft-14-reviewed.sqlite --search "Player Name"
uv run fantasy draft pick --db var/draft-14-reviewed.sqlite "Exact Player Name"
uv run fantasy draft undo --db var/draft-14-reviewed.sqlite
```

When your actual slot is known, run `fantasy draft set-slot --db
var/draft-14-reviewed.sqlite SLOT`. The number used in rehearsals was illustrative.
No slot has been assigned to your real session.

Private artifacts:

- `var/prepared-market-2026-09-10/board.json` and `board-with-reviews.csv`: prepared board and spreadsheet fallback.
- `var/prepared-market-2026-09-10/audit.json`: flags, position demand and watchlist.
- `private/draft-preparation-2026-09-10.json`: source-linked research notes and additions.
- `var/rehearsal-shadow-2026-09-10/seat-plans.md`: all-slot practice scenarios.
- `var/rehearsal-shadow-2026-09-10/usable-shadow.json`: separate strategy disagreements.
- `var/rehearsal-shadow-2026-09-10/report.json`: reproduction hash and workflow checks.

## Remaining before relying on recommendations

1. Replace the ranking proxy with current Yahoo rank/ADP and verify eligibility.
   A provider-authorized export or manual input works. The
   [Daily Faceoff projection tool](https://www.dailyfaceoff.com/tools/nhl-player-projections)
   documents exports and Yahoo ADP; account-gated data has not been obtained.
2. Supply complete rookie stat projections. Nine unranked players remain visible;
   they must not be treated as worthless or automatically ignored at draft time.
3. Review dated injury recovery and goalie workloads. Injury flags do not reduce
   appearances automatically. A ten-game sensitivity is a scenario, not a medical
   prognosis. Current-team changes also remain review flags, not fitted effects.
4. Resolve high-impact historical source disagreements before trusting narrow
   ranking differences. Existing flags remain visible; no provider is silently
   averaged with another.
5. Refresh news near the draft and choose the slot-specific plan when your slot
   is known. All-slot scenarios are conditional practice examples, not predictions
   of the exact players your friends will leave available.

The full-roster matching constraint guarantees room to fill required positions
when the simulated roster reaches 16 players. The real tracker permits recording
observed picks even if they produce a roster mismatch, and reports the mismatch.
Fourteen teams create demand for 56 active defensemen and 28 active goalies before
bench choices. Depth-surplus diagnostics ignore bench demand and can count a
multi-position player in more than one pool; do not use them as a standalone rank.

## Import contract

`prepare-draft` writes to a **new** directory and does not alter an existing draft.

```sh
uv run fantasy prepare-draft --board var/draft-baseline-fixed.json \
  --dossier private/draft-preparation-2026-09-10.json \
  --market private/market-espn-proxy-2026.csv --as-of 2026-09-10 \
  --teams 14 --output-dir var/NEW-PREPARED-DIRECTORY
```

Market CSV columns: `id,season,as_of,source,metric,value`. IDs use `nhl:12345`;
season uses `2026-27`; date uses `YYYY-MM-DD`. `metric` is `rank` or `adp`.
Use one source, date and metric per import. Reconcile IDs before import; name-only
or ambiguous matches are intentionally not accepted. Provider adapters can
convert permitted exports into this common format without changing analytics.

The dossier contains optional `additions`, `reviews`, and `projections` arrays.
Every record needs `id`, `season`, `as_of` and `source`:

- Additions also need `name`, `kind`, `positions`, and preferably `team`. Use a
  verified NHL ID. Primary positions stay explicitly unverified for Yahoo.
- Reviews need `status` (`injury_review`, `role_review`, `identity_review`, or
  `reviewed`) and `note`. Eligibility changes additionally require `positions`
  and `position_provider: "Yahoo"`, with an appropriate evidence source.
- Projections need `basis: "season_total"`, `games`, and `stats` containing every
  nonzero-weight stat in this league. The tool recomputes fantasy points and
  preserves the historical baseline for comparison. It does not accept a generic
  provider fantasy score as a substitute for stat projections.

To add a missing identity to an ongoing session, place one addition record in a
JSON file, then run:

```sh
uv run fantasy draft add-player --db var/draft-14-reviewed.sqlite \
  --input private/missing-player.json --as-of 2026-09-13
```

The addition is unranked and audited. Existing picks are preserved. Use `draft
positions` for later verified eligibility corrections. For a backup, close active
commands and copy the SQLite file; the JSON export is an inspection fallback,
not an automatic restore format.

Validation: 71 tests pass. The separate shadow comparison changed the top choice
at 4 of 56 opening-round checkpoints. This is a disagreement audit, not a test
of actual 2026-27 outcomes. The CSV fallback includes source-linked review notes
and ranking provenance, with spreadsheet formula injection protection.

## Contextual review is a core requirement

Tristan emphasized that changing roles, recovery, and opportunity are a primary
reason to build this tool. Treat contextual review as part of projection design,
not an optional generic rating bonus. A trade by itself does not justify a downgrade.
Separate verified events, expected deployment changes, stat effects, and confidence.
Keep conflicting evidence and review dates visible. Avoid counting the same role
change in both an appearance adjustment and a second arbitrary bonus/penalty.

The first private review is `var/context-review-2026-09-10-v2.md`, covering four
cases with sourced facts and unresolved deployment questions. Its numerical cases
are historical workload plus/minus ten appearances at fixed rates. They are
sensitivity checks, not evidence-based low/base/high forecasts or medical timelines.
The next step is dated deployment evidence for PP/non-PP exposure and joint goalie
start allocation, then scenario assumptions that can be reviewed and backtested.
The live board is unchanged by this report. All 72 tests pass.
