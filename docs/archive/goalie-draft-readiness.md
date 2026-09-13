# Goalie roles and the actual schedule, September 10, 2026

The initial review below is preserved as history. The [completed review](goalie-review-complete.md)
now covers all 62 goalies; use `private/goalie-workload-review-2026-09-10-v2.json`.

There is now a reproducible local command to evaluate a goalie combination on
the upcoming schedule. The draft guide can also display dated workload review
notes alongside its baseline rankings. No live player projections were replaced.

## Schedule acquisition and validation

The [NHL schedule announcement](https://frontend.d3.nhle.com/es/news/la-nhl-anuncia-el-calendario-completo-de-la-temporada-2026-27)
links an official downloadable PDF. Its extracted list pages did not provide
complete reciprocal entries for Vegas, so the strict document importer rejected
it. This is a text-extraction/source-completeness issue, not a claim that the
NHL has scheduled contradictory games. The original PDF and extracted text are
preserved privately for inspection.

The fallback uses the NHL website's public club-schedule JSON endpoint, for example
[Winnipeg's schedule](https://api-web.nhle.com/v1/club-schedule-season/WPG/20262027).
This is an **undocumented public endpoint**, not a supported developer API or a
promise of ongoing access. The adapter can be replaced with a permitted export.
No authenticated pages or Yahoo scraping are involved. Downloads are cached with
source URLs, retrieval timestamps and hashes, requested sequentially with a pause,
and never committed. A failed download can resume using the same snapshot folder.

All 32 club responses agreed on 1,344 regular-season games, 84 per team, from
September 29, 2026 through April 10, 2027. Checks reject conflicting dates,
duplicate team/game observations, missing reciprocal records and incomplete
season totals. Game IDs remain NHL IDs; document-only composite keys have a
separate prefix. Dates use NHL `gameDate`, not a conversion from UTC.

Reproduce from the existing cache into a new output file:

```bash
uv run python -m tools.fetch_nhl_schedule \
  --directory snapshots/2026-09-10/nhl-schedule/api \
  --output var/schedule-20262027-repeat.json
```

Use a new dated snapshot directory to refresh. A snapshot is not a live feed.

## Workload review

The private review inventories 62 board goalies. Twenty have explicit source-backed
role scenarios across 11 teams. The other 42 remain visibly unreviewed or
unallocated, including players missing from the usable forecast pool. This is a
prioritized first pass, not a medical clearance review of every goalie.

The most consequential findings:

- Skinner's old workload carried over roughly 52 appearances, while the
  [Winnipeg roster report](https://frontend.d3.nhle.com/news/topic/team-resets/winnipeg-jets-roster-changes-for-2026-27-season)
  describes him as Hellebuyck's backup. Our conditional allocation is 64/16 starts,
  with four for other goalies. These numbers are analyst assumptions, not a team promise.
- [Minnesota's preview](https://frontend.d3.nhle.com/news/topic/32-in-32/minnesota-wild-three-questions-for-2026-27-season-32-in-32)
  supports testing reduced Gustavsson availability and a larger Wallstedt role.
  The working scenario uses 50 Wallstedt starts and 26 Gustavsson starts; remaining
  starts cover other goalies. There is no inferred medical return date.
- [Vancouver's preview](https://frontend.d3.nhle.com/news/topic/32-in-32/vancouver-canucks-three-questions-for-2026-27-season-32-in-32)
  leaves Demko's timeline uncertain. The scenario uses 36 Demko starts, 38 Lankinen
  starts and the remaining ten for other goalies. It is not a prediction of recovery.
- [NHL editorial goalie projections](https://frontend.d3.nhle.com/news/topic/fantasy/2026-2027-fantasy-hockey-goalie-win-projections)
  provide role-review signals for Colorado, Carolina, Montreal, New Jersey,
  Toronto, Philadelphia, St. Louis and Vegas. Editorial win estimates are not
  converted mechanically into start forecasts or treated as coach commitments.

Every allocation leaves an explicit reserve balance to total 84 team starts.
Unreviewed teams use historical appearance shares capped at 78 starts with at
least six reserved; that is a placeholder heuristic, not verified deployment.
The downside case reduces each named goalie's starts by 25%, transferring the
balance to unowned reserve goalies. It is an exposure stress test, not an injury
probability or a claim that all goalies will deteriorate together. Rates remain
historical per-appearance rates, which can differ from conditional starter rates.

Private artifacts:

- `private/goalie-workload-review-2026-09-10.json`: evidence, assumptions, allocations and review dates.
- `var/goalie-workload-review-2026-09-10.csv`: readable review queue.
- `var/goalie-weeks-pilot-2026-09-10-v2.json`: paired baseline/downside examples and input hashes.

## Commands for the draft

Display the role review without changing the board or draft session:

```bash
uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite \
  --goalie-workloads private/goalie-workload-review-2026-09-10.json
```

Evaluate a specific combination, here Hellebuyck and Wallstedt:

```bash
uv run fantasy goalie-weeks \
  --schedule var/schedule-20262027-2026-09-10.json \
  --workloads private/goalie-workload-review-2026-09-10.json \
  --goalies nhl:8476945 nhl:8482661 --as-of 2026-09-10
```

Add `--case downside` for the workload stress or `--json` for the full report.
The report includes weekly team games, back-to-backs, daily slot clashes,
expected starts, physically impossible minimums and a failure-probability proxy.
The existing `draft-guide --goalie-calendar` remains a historical insurance
experiment; use `goalie-weeks` for the upcoming calendar.

## What the examples show

| Combination | Baseline expected failed calendar weeks | Downside |
| --- | ---: | ---: |
| Hellebuyck / Skinner | 8.1 | 17.8 |
| Hellebuyck / Wallstedt | 4.1 | 9.9 |
| Hellebuyck / Wallstedt / Wedgewood | 2.6 | 6.6 |
| Gustavsson / Demko | 17.0 | 21.8 |

These are scenario outputs across 28 Monday-Sunday calendar buckets, **not
predicted Yahoo failed weeks**. Yahoo may combine break weeks and use different
opening/playoff periods. The February 1 bucket is physically insufficient even
for several otherwise strong combinations. Actual Yahoo matchup boundaries are
still needed before declaring that week actionable.

Same-team goalies share one start per NHL game. Owning both Winnipeg goalies
cannot create three starts during a two-game Winnipeg week. A cross-team pair
can cover more dates. A third goalie helps, but these examples do not price its
lost skater slot or draft cost and are not draft recommendations.

Daily lineup selection uses expected points and two goalie slots. It does not
optimize the whole week's lineup or react to confirmed starters. The report
separates physical capacity from selected-lineup opportunities because selecting
two same-team goalies can leave a different-team goalie benched. Independent
start events omit prolonged injury dependence, relief appearances and rate
uncertainty. The engine supports explicit contiguous absence blocks, but the
pilot does not invent them from uncertain medical timelines.

## Next

1. Refresh the twenty reviewed roles and finish the high-priority unreviewed
   goalies before September 13, especially injury and trade-sensitive inputs.
2. Replace placeholder appearance rates with supported per-start rates where
   available, preserving uncertainty for small samples.
3. Import actual Yahoo matchup dates when available. Keep calendar and league
   weeks separate until then.
4. Compare a third goalie against a skater plus a later goalie, including lineup
   choices that deliberately improve weekly minimum coverage. No waiver policy
   is assumed while acquisition timing remains unknown.
