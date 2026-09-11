# First study review, September 10, 2026

Only two target seasons have been drafted and scored: 2024-25 (model selection)
and 2025-26 (later evaluation). 2023-24 supplied prior observations. Eight models
had 125 tuning scenarios each; the locked winner had 125 later scenarios, each
paired with a baseline. These are repeated drafts, not 1,125 independent seasons.
No pre-2024 target season or daily H2H season replay has been run.

## Outcome correction

The missing selected-policy outcome was one player, Barkov, present in 60 rosters
versus 23 benchmark rosters. NHL reporting confirms he missed 2025-26 entirely.
[Official report](https://www.nhl.com/news/healthy-aleksander-barkov-raring-to-go-for-panthers-after-knee-injury)

A sourced private correction sets his realized NHL games and points to zero.
`archive/tg/personal/experiments/audit_draft_study.py` rescores the saved picks after the draft, without
changing forecasts, picks, model selection, or the original report. It never
blanket-fills missing outcomes with zero. Private inputs and results:

```sh
uv run python archive/tg/personal/experiments/audit_draft_study.py var/draft-study.json \
  private/outcome-corrections-2025.json var/draft-study-audit.json
```

| Evaluation | Complete pairs | Mean full-roster point gain |
| --- | ---: | ---: |
| Original, missing records excluded | 65 | 387.2 |
| Corrected, confirmed zero included | 125 | 84.7 |

The corrected gain is approximately 1.0% of benchmark points. It is positive in
78/125 scenarios, ranges from -1,100.3 to +925.8, and averages +46.0 in 12-team
leagues and +120.5 in 13-team leagues. These correlated scenarios do not establish
statistical significance or a fantasy win probability. The tuning gain was only
35.0 points. Current pool/eligibility bias remains after the correction.

## Candidate mechanisms and concerns

- Rate shrinkage treats 20 games of historical positional average as additional
  evidence. The strength of this assumption is not independently established.
- Workload regression moves historical appearances halfway toward a fixed 70
  games for skaters or 45 for goalies. It increases some forecasts as well as
  reducing others. These targets were supplied assumptions, not fitted workloads.
- In the 2025 draft experiment, Kaprizov's appearances increase from 49.5 to
  59.75, while his rate falls from 11.85 to 11.15 points/game. His total rises
  from 586.4 to 666.2. Vasilevskiy's workload falls from 60.25 to 52.625, lowering
  his total from 693.8 to 592.8. This can prefer rebound skaters over workhorse
  goalies regardless of whether current role evidence supports that choice.
- Drafted-player contribution accounting attributes +527.4 points to the change
  in Kaprizov selection frequency alone, exceeding the +84.7 net gain. Other
  selection changes offset it. This is not a causal estimate, but highlights
  sensitivity to individual players and one year's outcomes.
- A historical draft needs an exact timestamp. A known injury before that date
  is actionable information; an injury afterward is an outcome the manager
  could not have known. Current experiments filter seasons, not dated news.
- Whole-roster production credits bench points. Synthetic opponent preferences
  do not represent Yahoo ADP. The study cannot yet identify real market bargains,
  model goalie minimums, or compare actual weekly lineup value.

What works: deterministic paired drafts, separate forecasts/outcomes, explicit
missingness, retained picks, source receipts, and an audit that exposes an
inflated result rather than silently preserving it. No candidate is promoted.

## Extending toward 2015

[MoneyPuck's download catalogue](https://moneypuck.com/data.htm) lists season and
game-level datasets back through 2008-09, including 2015-16. It is a promising
permitted analytical-history source. The inspected season schemas do not supply
all our required official scoring components, so it is not a complete solution.

[Hockey Insights' historical catalogue](https://hockeyinsights.ca/opendata/)
offers 2016-17 onward, but its history file contains leader subsets, including
only 50 skaters and 15 goalies per year. It cannot supply a historical draft pool.
Using its later winners as the draft universe would introduce severe leakage.

[Elite Prospects' 2015-16 page](https://www.eliteprospects.com/league/nhl/stats/2015-2016)
shows export controls, but the displayed fields do not cover all our scoring
needs. Export access and reuse permission still need verification. No gated
export was accessed. NHL public endpoint bulk-use permission remains unresolved,
as recorded in data-sources.md. No older complete dataset was imported this pass.

Target 2015-16 through 2025-26, with earlier history for the first draft. A
three-year warm-up needs 2012-13 onward, including shortened-season handling.
Use growing historical development windows and freeze each forecast before the
next season. Reserve an uninspected period when possible; periods already used
to revise the model are development data even if chronologically later.

Treat shortened 2019-20 and 2020-21 separately, normalize appearances by schedule
opportunities, and report both all-season and ordinary-season results. Historical
league sizes and changing scoring environments also need explicit treatment.
First expand complete raw scoring coverage and player universes, then replay
lineups and weekly rules, before increasing the model search space.
