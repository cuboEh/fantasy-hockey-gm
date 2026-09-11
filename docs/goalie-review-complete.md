# Remaining goalie review completed, September 10, 2026

All 42 entries from the first review queue have been assessed. The combined file
now has 61 source-backed conditional scenarios and one reviewed but unresolved
entry, Connor Ingram. Reviewed means the role was investigated, not that starts,
health, job security or performance are guaranteed.

The private [complete table](../var/goalie-review-complete-2026-09-10/review.md)
contains all 62 players, source links, roles and baseline/downside start counts.
Its companion `goalies.csv` is suitable for draft-day reference. Downloaded data
and personal artifacts remain excluded from Git.

## Important changes

- **Greaves, Askarov and Silovs:** old workload averages can lag a changing role.
  Our conditional baseline now uses 54, 48 and 44 starts respectively. These are
  analyst allocations informed by the [Columbus preview](https://frontend.d3.nhle.com/news/topic/32-in-32/columbus-blue-jackets-fantasy-projections-for-2026-27-season-32-in-32),
  [San Jose roster review](https://frontend.d3.nhle.com/news/topic/team-resets/san-jose-sharks-roster-changes-for-2026-27-season)
  and [Pittsburgh preview](https://frontend.d3.nhle.com/news/topic/32-in-32/pittsburgh-penguins-three-questions-for-2026-27-season-32-in-32).
  Silovs still faces prospect competition; this is not a secure-workhorse label.
- **Andersen:** the [August 26 report](https://frontend.d3.nhle.com/news/frederik-andersen-mattias-janmark-expected-to-miss-training-camp-for-edmonton-oilers)
  says he is expected to miss camp after an offseason training injury. The 30/15
  baseline/downside starts are exposure scenarios, not a medical return forecast.
- **New Jersey:** the [September 9 report](https://frontend.d3.nhle.com/news/new-jersey-devils-latest-to-try-3-goalie-system-entering-training-camp)
  describes competition involving Allen, Rittich and Daws. Allen's earlier
  allocation was revised from 50 to 44 starts; Rittich has a 16-start baseline
  and zero-start job-loss stress. Twenty-four starts remain reserved for Daws
  and other goalies missing from the board. No camp winner is assumed as fact.
- **Montembeault:** the previous name-based setup missed the board's “Samuel”
  when looking for “Sam.” Matching by NHL player ID restores his 12-start
  conditional allocation, with a zero-start downside. The
  [Montreal preview](https://frontend.d3.nhle.com/news/topic/32-in-32/montreal-canadiens-three-questions-for-2026-27-season-32-in-32)
  supports continued competition with Dobes and Fowler. Missing board competitors
  retain their share in the reserve bucket.
- **Contested backups:** small guaranteed-looking workloads were misleading.
  Several now have explicit zero-start downside cases. For example, Tampa's
  [goalie discussion](https://frontend.d3.nhle.com/sv/news/fem-fragor-for-tampa-bay-lightning-infor-sasongen-2026-27)
  supports considering both Johansson and Hildeby behind Vasilevskiy.
  A zero scenario is not a prediction that the player will never appear.
- **Ingram:** the [Edmonton roster review](https://frontend.d3.nhle.com/news/topic/team-resets/edmonton-oilers-roster-changes-for-2026-27-season)
  listed him as an unrestricted free agent departing the club. This research
  did not establish a current job. His board team remains explicitly last-known,
  and his start scenarios remain null. The coverage command rejects him rather
  than interpreting unknown opportunity as zero.

Other entries were assessed against the NHL's dated team previews and
[editorial goalie outlook](https://frontend.d3.nhle.com/news/topic/fantasy/2026-2027-fantasy-hockey-goalie-win-projections).
Editorial rankings and win estimates support a role assessment but are not
converted into reported start forecasts. No absence of injury news is treated
as medical clearance. The general downside remains a 25% exposure reduction;
contested jobs and recovery cases have explicit, more severe assumptions.

## Use the completed review

```bash
uv run fantasy draft-guide --db var/draft-14-reviewed.sqlite \
  --goalie-workloads private/goalie-workload-review-2026-09-10-v2.json

uv run fantasy goalie-weeks \
  --schedule var/schedule-20262027-2026-09-10.json \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --goalies nhl:8476945 nhl:8482661 --as-of 2026-09-10
```

Add `--case downside` to compare the stress case. The old v1 file is preserved
for reproducibility. Current board points, historical studies and draft picks
are unchanged; selecting the v2 file enables the updated advice.

Audit or regenerate the complete table into a new directory:

```bash
uv run python -m tools.audit_goalie_workloads \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --board var/prepared-market-2026-09-10/board.json \
  --as-of 2026-09-10 --output-dir var/goalie-review-repeat
```

The audit checks exact coverage of the board's goalie IDs, unchanged teams and
rates, dated evidence, duplicate IDs, null unresolved workloads and both baseline
and downside team budgets summing to 84. Both consumers validate v2 ledgers.
All 61 usable players were exercised in baseline and downside reports on the
upcoming calendar, for 122 smoke checks. Ingram's rejection was also verified.
This verifies operation and consistency, not projection accuracy or a new
historical performance gain.

The remaining uncertainty is camp deployment, medical updates and unconfirmed
Yahoo matchup boundaries. Refresh evidence before the draft and continue to
separate calendar-week coverage estimates from actual league matchup rules.
