# Six-step historical evaluation implementation

Updated September 10, 2026. The research pipeline now connects historical records,
mock drafts, daily lineups, weekly scoring, streaming, and dated market inputs.
It is not a faithful reconstruction of every historical Yahoo league. No model
has been promoted to the current draft board.

## 1. Historical scoring coverage

Published SportsDataverse releases supply separate skater box scores, goalie box
scores, goal/assist events and schedules. Fourteen seasons ending 2013 through
2026 were downloaded and normalized. Eleven target seasons, 2015-16 through
2025-26, have three prior seasons available for initialization.

Sources and attribution:

- [SportsDataverse NHL producer](https://github.com/sportsdataverse/fastRhockey-nhl-data)
- [Published player data](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nhl_skater_boxscores)
- [Published goalie data](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nhl_goalie_boxscores)
- [Published scoring events](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nhl_scoring)
- [Published schedules](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nhl_schedules)
- [Repository license](https://github.com/sportsdataverse/sportsdataverse-data/blob/main/LICENSE)

These are third-party published datasets derived from NHL records, not an
NHL-supported developer API. Retrieval uses published downloads, not NHL/Yahoo
page scraping. Raw files and receipts remain in ignored dated snapshots.

The adapter joins by game and player IDs, excludes playoffs and shootout goals,
normalizes season-ending years, and converts game timestamps to Edmonton dates.
Power-play points come from credited goal scorers and assists on PP events.
Shutouts require no opposing non-shootout goals and only one appearing goalie
for that team. They are derived, not a source-provided official shutout field.

The older combined player files lacked game IDs. Separate skater files resolved
that issue. Some older assist columns contain a Polars text rendering rather
than JSON; a bounded parser verifies the declared helper count. Unknown formats
fail. Game/team coverage, identity uniqueness and numeric inputs are checked.

Some source counts disagree: goalie shots versus saves plus goals allowed, a few
scoring-event/box-score differences, and one zero-TOI scoring appearance. Original
counts are retained with explicit conflicts, never averaged or silently repaired.
Consequently, "complete game coverage" does not mean "verified official stats."
The normalized dataset and result reports retain these conflicts. Matchup clean
comparisons exclude affected weeks and report that exclusion.

## 2. Draft connected to daily replay

The player universe is drawn from the preceding three regular seasons. It
includes players who subsequently stopped playing, improving on the earlier
current-player survivor pool, but does not include rookies with no prior NHL
history or every pre-draft status announcement. Eligibility is the last recorded
NHL primary position, not historical Yahoo multi-position eligibility.

Forecasts see only earlier seasons. Historical appearances are scaled by the
completed team's schedule for shortened-season comparability. The last team's
schedule is a proxy for traded players. Target forecasts use a common 82-game
basis; the actual target calendar controls realized opportunities. Original
preseason schedule publication and postponement knowledge are not archived.

Each mock roster is replayed through the real game's daily dates. At the first
game of each day, the policy selects active players from expected per-appearance
points and historical appearance probability. Bench production is separate.
Actual points are revealed afterward. Team changes are learned only after the
player appears in a new team's records. This is deliberately lagged inference,
not a dated trade/news feed. Daily forecasts otherwise remain frozen.

The policy acts before the earliest game, a restricted strategy compatible with
player-game-time locks, not a full Yahoo rolling-lock implementation. It never
uses actual starting goalie identities to choose that day's lineup.

## 3. Weekly rules and separate active management

Yahoo's [minimum goalie appearance guidance](https://help.yahoo.com/kb/SLN6878.html)
confirms active goalie appearances count together, and failure removes points
for goalie performance. This is now applied while preserving skater points.
The old output key `zero_goalie_penalty_scenario` is retained for compatibility;
it implements the verified rule rather than an unresolved penalty assumption.

[Yahoo lineup deadlines](https://help.yahoo.com/kb/fantasy-hockey/sln6775.html)
identify player-game-time lineup locks and immediate Daily-Today roster updates.
An older [details page](https://hockey.fantasysports.yahoo.com/hockey/details/weekly_deadline)
mentions a five-minute transaction cutoff. The simulator acts before games and
does not attempt either platform's near-lock edge cases.

IR activation/status and the actual Yahoo cannot-cut list are not reconstructed.
Fixed-roster performance and active management are evaluated from identical draft
picks. Streaming checks marginal usable points through the week's end, with a
simple opportunity-cost adjustment and four weekly acquisitions by default.
At most one move is made before a day's first game. Other teams retain drafted
ownership. The first two picks are protected as a synthetic safeguard, not a
reconstructed Yahoo can't-cut list.

Waiver delay is configurable, defaults to a two-day cooldown on dropped players,
and is not a claim-priority simulator. The league's exact waiver settings remain
pending. Undrafted players are assumed free by the first season game. No claim
is made that every simulated move would be legal in the user's Yahoo league.
Monday-Sunday weeks are reconstructed, without actual fantasy playoffs.

`research/score_matchups.py` additionally scores fixed versus active management
against synthetic round-robin opponents, including byes for 13 teams. Opponents
use fixed rosters and their own daily lineup policy. Source-conflict weeks are
excluded and counted. These are hypothetical H2H records, not historical Yahoo
standings or playoff results.

## 4. Chronological expansion and evaluation

The earlier 12/13-team comparison runs 2015-16 through 2025-26, two opponent seeds, 12/13
teams, and early/middle/late seats. Four policies yield 528 draft scenarios.
Another 132 replays compare streaming with fixed management from baseline picks.
Repeated seeds and seats share NHL outcomes and are not independent seasons.

The study covers normal and shortened seasons; aggregate reporting separates
2019-20 and 2020-21. A walk-forward accounting chooses the policy with the best
mean result in earlier target seasons before evaluating the next one. Since
these policies were developed during research and some periods were previously
inspected, this is not an untouched holdout or evidence of calibrated accuracy.
No automated deployment gate accepts these research reports.

## 5. Small policy comparison

- Historical production baseline.
- Rate shrinkage and historical usage-cohort workload regression.
- Simple positional replacement ordering.
- Marginal usable-game draft value, using the previous season's calendar only.

The usable-game policy examines twelve fitting candidates from the production
ranking and values added active-slot production relative to the roster already
drafted. It penalizes crowded nights without seeing the target year's outcomes.
It is a heuristic, not a global draft optimizer. The previous calendar is a
proxy; a permitted preseason target schedule would be a better production input.

The private `var/multi-season-review.md` reports yearly differences and caveats.
Across two seeds, mean minimum-adjusted lineup gains versus baseline were +413.4
for usable-game drafting, -112.8 for workload cohorts, and -155.3 for replacement
ordering. The usable-game yearly mean was positive in all eleven targets, but
some individual seeds and seats lost. Excluding shortened seasons gives +411.9.
Streaming averaged +584.8 in its separate experiment. These estimates retain
source and simulation limitations and are not production performance promises.
Do not add its draft-policy and streaming gains together: they are separate
experiments, not a tested combined strategy.

## 6. Dated draft-market data

A [2024 CSG draft workbook shared by its author](https://www.reddit.com/r/fantasyhockey/comments/1fpy57m/)
was downloaded. Its cached Yahoo ADP column yielded 249 unambiguous historical ID
matches; nine names remained unmatched. The workbook labels a September 25,
2024 update and was posted September 26. These support historical use but do not
prove an immutable archive or independently verify each ADP value.

The workbook was read as ZIP/XML, with no macros, formulas or external links
executed. Position columns were not imported because the displayed platform
selection was not clearly Yahoo. Market files preserve source, season, metric
and as-of date. Wrong-season or post-draft market rows fail validation.

A separate 2024-25 sensitivity run uses the matched market values for opponents
and an explicitly synthetic fallback for uncovered players. This is incomplete
market coverage, not a full historical Yahoo market reconstruction. Market ranks
never change fantasy scoring or production rates. Rank gaps are not calibrated
probabilities of availability at the next pick.

## Reproduce

Use fresh output directories to preserve previous runs. Published release years
are season-ending years, so `2025` means 2024-25.

```sh
uv run python research/fetch_history.py --directory snapshots/NEW-DATE/sportsdataverse \
  --years 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 \
  --datasets skater_box goalie_box scoring schedule
uv run python -m fantasy_hockey.history --directory snapshots/NEW-DATE/sportsdataverse \
  --config config.local.toml --years 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 \
  --output-dir var/new-history
uv run python -m fantasy_hockey.seasonlab --history-dir var/new-history \
  --config config.local.toml --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 \
  --teams 14 --seed 0 --waiver-days 2 --max-acquisitions 4 --output-dir var/new-study-seed0
```

Repeat with seed 1 and a separate output directory. Then:

```sh
uv run python research/summarize_seasons.py --studies var/new-study-seed0 var/new-study-seed1 \
  --output var/new-review.json
uv run python research/score_matchups.py --study-dir var/new-study-seed0 \
  --history-dir var/new-history --config config.local.toml --output var/new-matchups.json
```

For market sensitivity, use `archive/tg/personal/experiments/import_csg_market.py` on the saved workbook,
then supply `--market-csv`, one target `--years 2025`, and an explicit compatible
`--draft-date 2024-09-27` to seasonlab. This historical example date is not the
user's current September 13 draft date.

Remaining limits are source reconciliation, rookie and dated injury coverage,
Yahoo historical eligibility, original schedule snapshots, competing active
opponents, actual waiver priority, and user-specific playoff calendars. These
are recorded limitations, not silently completed steps.

## Current league size and opponent assumptions

Tristan selected 14 teams on September 10. The season replay CLI now defaults
to 14; `--teams 12 13` reproduces the earlier league-size scenarios explicitly.
The local current tracker is `var/draft-14.sqlite`, with 16 rounds and 224 picks.
Earlier databases and study outputs are preserved.

Opponents follow a fixed ranking with persistent preference variation and roster
fit constraints. They do not run our usable-game optimizer or anticipate our next
pick. Without a dated market export, the ranking is a historical-points proxy,
not Yahoo draft-room order. A permitted current Yahoo ranking/ADP export would
make that behavior a closer match to friends choosing the next rated player.
No extra strategic opponent complexity is planned for the immediate draft.

The 14-team rerun covers 264 drafts across 2015-16 through 2025-26, four policies,
two opponent seeds and seats 1, 7 and 14. Mean goalie-minimum-adjusted lineup
points versus the baseline: usable-game drafting +426.5 (10/11 positive season
averages), cohort workload -135.0, replacement -206.6. Separate streaming from
the same baseline picks averaged +550.7; do not add this to draft-policy gains.
Results remain research comparisons, with the limitations above. No model was
promoted to the live board. Private details: `var/14-team-review.md`.
