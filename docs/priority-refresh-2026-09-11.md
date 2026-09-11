# Priority-player evidence refresh

Reviewed September 11, 2026, following the final-roster and sensitivity audit.
Seven players now have dated review notes in the dashboard's existing player
details. Numerical forecasts, ranks, eligibility and model weights are unchanged.
An editorial preview is evidence to compare, not a confirmed lineup or medical
clearance. Targeted searches did not establish a decisive newer official update;
that does not mean there is no injury or role risk.

## Independent forecast comparisons

Skater points below mean NHL goals plus assists, not this league's fantasy points.
Goalie figures are wins, not starts or appearances. Sources are official NHL
editorial pages published in August 2026 and revisited on September 11.

| Player | Metric | Working projection | NHL reference | Source |
| --- | --- | ---: | ---: | --- |
| John Gibson | Wins | 27.335 | 26 | [Detroit, August 10](https://www.nhl.com/news/topic/32-in-32/detroit-red-wings-fantasy-projections-for-2026-27-season-32-in-32) |
| Jet Greaves | Wins | 28.3285 | 25 | [Columbus, August 8](https://www.nhl.com/news/topic/32-in-32/columbus-blue-jackets-fantasy-projections-for-2026-27-season-32-in-32) |
| Joey Daccord | Wins | 26.341 | 20 | [Seattle, August 24](https://www.nhl.com/news/topic/32-in-32/seattle-kraken-fantasy-projections-for-2026-27-season-32-in-32) |
| Dustin Wolf | Wins | 26.109 | 20 | [Calgary, August 4](https://www.nhl.com/news/topic/32-in-32/calgary-flames-fantasy-projections-for-2026-27-season-32-in-32) |
| Dylan Cozens | NHL points | 60 | 61 | [Ottawa, August 20](https://www.nhl.com/news/topic/32-in-32/ottawa-senators-fantasy-projections-for-2026-27-season-32-in-32) |
| J.T. Miller | NHL points | 72 | 62 | [Rangers, August 19](https://www.nhl.com/news/topic/32-in-32/new-york-rangers-fantasy-projections-for-2026-27-season-32-in-32) |
| Dougie Hamilton | NHL points | 49 | 46 | [Devils, August 17](https://www.nhl.com/devils/news/topic/10-takeaways/new-jersey-devils-fantasy-projections-for-2026-27-season-32-in-32-x3700) |

## Implications for our decisions

The working values come from the frozen DtZ import, rescored locally. Neither
provider is treated as ground truth, and the comparisons are not independent
realized outcome validation.

- Daccord and Wolf need caution in close comparisons. Replacing only the win
  component with the reference value would reduce their season FP by 31.705 and
  30.545 respectively. These are isolated accounting differences with all other
  statistics fixed, not complete alternative forecasts or weekly usable values.
- Miller's offensive forecast disagreement warrants review before interpreting
  his existing minimum-regret result as a safe choice. Our board has no equivalent
  transferred skater downside for him. Do not manufacture a confidence interval.
- Cozens' 84 projected games constitute a full-season availability assumption.
  Pure-center roster congestion remains relevant even if his offensive forecast
  agrees with another source. Face-off wins do not score in this league.
- Hamilton's 79 GP and 18 PPP remain forecast assumptions. Confirm special-teams
  deployment as usable evidence appears rather than inferring PP1 security from
  a generic ranking.
- Gibson/Greaves still need start-share and rate uncertainty assessed separately.
  The prior two-goalie pair's 1.24 FP baseline lead is too small to carry a strong
  recommendation without comparable uncertainty for the skater alternative.

No new injury discount, start allocation or numerical boost was justified by this
bounded review. The existing conditional workload cases remain labeled as such.
The next evidence refresh should occur before draft time, particularly if camp
reports or official health updates change a selected player's outlook.

## Session and artifacts

Tristan confirmed the seven existing picks were tests. They were removed with
seven revision-checked undo operations after a consistent SQLite backup. The
session now has zero picks and an unset slot. Audit history is preserved.

Local, ignored artifacts:

- `snapshots/2026-09-11/test-picks-cleared-203314/before.sqlite` and `receipt.json`.
- `snapshots/2026-09-11/priority-role-refresh/review.json`: dated evidence,
  forecast comparisons, questions and explicit unknowns.
- `snapshots/2026-09-11/priority-role-refresh/before-notes.sqlite`.
- `snapshots/2026-09-11/priority-role-refresh/reviewed-board.json`: board including
  the seven new review notes. The original frozen board remains intact.

The review-note transaction moved the session to revision 15, invalidating older
cached comparison results. Assertions verified that only review histories changed,
with every numeric forecast, eligibility field, setting and pick preserved.
No application code or scoring logic changed, so this did not require a new model
simulation campaign. Historical participation repair remains the next validation
step; team diversification is recorded as a deferred hypothesis in the product plan.
