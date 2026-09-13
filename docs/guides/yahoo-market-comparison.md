# Yahoo value-versus-market comparison

September 11, 2026. This increment delivers a reviewable comparison board, not
another optimizer. It reuses the existing scorer, historical board, reviewed
context cases, starter estimates and cached identity data. Live draft picks,
rankings, and prospective snapshots remain unchanged.

## Open the result

Local generated files are deliberately ignored by Git:

- `var/yahoo-market-comparison-2026-09-11-v3/comparison.csv`: all 390 rows, sortable
  in a spreadsheet, with Yahoo eligibility, displayed rank, preseason ADP, ADP,
  drafted percentage, baseline production/rank, scenario production/rank and flags.
- `var/yahoo-market-comparison-2026-09-11-v3/comparison.md`: selected disagreements,
  scenario examples, and missing estimates.
- `var/yahoo-market-comparison-2026-09-11-v3/comparison.json`: full provenance,
  source hashes, identity matches and existing scenario notes.
- `var/yahoo-market-comparison-2026-09-11-v3/identity-eligibility-review.json`:
  position differences, missing projections and team conflicts for review.

## Findings

All **390 names** match a unique cached NHL identity after using full normalized
name and forward/defense/goalie position family. The two Elias Pettersson identities
are distinguished by the supplied center eligibility. The 43 names absent from
the baseline board were found in existing MoneyPuck files. These are source-backed
name matches, not an authenticated Yahoo-player-ID crosswalk. No Yahoo IDs were
invented and no external collection was needed.

There are **264 populated ADP pairs**, **338 historical production estimates**,
and **52 players without those estimates**. The latter include 43 absent board
players and nine existing unprojected entries. Missing values remain blank in CSV
and null in JSON. Missing ADP does not mean undraftable or free, and missing
production does not mean zero value.

The comparison records **125 eligibility differences** among the original matched
board entries, plus Yahoo eligibility for the additional identities. Position
families and uniqueness were checked. User-supplied Yahoo positions are the
comparison's season-specific eligibility source; the old primary positions remain
alongside them so each change is inspectable. They were not independently fetched
from Yahoo and have not yet been merged into the live tracker.

Two team conflicts remain explicit: Luke Evangelista is NSH in the old board and
NJ in the pasted table; Eeli Tolvanen is SEA versus NYR. Alias normalization handles
TB/TBL, NJ/NJD, SJ/SJS and LA/LAK separately. A real team conflict must not silently
change a schedule or workload assumption.

## How to interpret the values

The historical baseline ranks all 461 projected players in the original
470-player board. It is league-scored season-total production, not usable-lineup
or replacement-adjusted value. Yahoo's market population and scoring formats
are not necessarily the same. An ADP-minus-rank gap is a review signal, not a
measured profit or proof of an edge.

Separate columns reuse the already reviewed goalie workloads and starter rates,
and explicitly selected skater context scenarios. They are conditional totals,
not calibrated probabilities. This reuse matters: Jarvis moves from historical
rank 36 to baseline-case rank 116, compared with ADP 121.6. The apparent historical
bargain mostly disappears under that injury scenario. Wallstedt moves from
historical rank 419 to scenario rank 93, versus ADP 60.1. Both examples show why
raw historical disagreement must not become an automatic recommendation.

Tom Wilson, Travis Konecny and Andrei Svechnikov are examples of historical-baseline
ranks substantially earlier than ADP. They warrant workload, source, role and
scoring review; they are not endorsed picks from this comparison alone. The
summary uses a 50% drafted threshold to avoid leading with low-participation
averages. That threshold is an editorial filter, not a modeled confidence level.
The CSV retains every supplied row, including low drafted percentages.

## Reproduce locally

```bash
uv run fantasy compare-market \
  --snapshot snapshots/2026-09-11/yahoo-user-supplied/draft-analysis-20262027-confirmed.json \
  --board var/prepared-market-2026-09-10/board.json \
  --catalog snapshots/2026-09-10/moneypuck/skaters.csv snapshots/2026-09-10/moneypuck/goalies.csv \
  --workloads private/goalie-workload-review-2026-09-10-v2.json \
  --rates var/goalie-start-rates-2026-09-10.json \
  --context var/context-pilot-2026-09-10-v3.json \
  --case-map private/draft-context-case-map-2026-09-10.json \
  --output-dir NEW_OUTPUT_DIRECTORY
```

Omit all four optional scenario inputs for the historical-only comparison. Each
run writes a new output directory and hashes its inputs. It does not open or edit
a draft database. All **122 tests pass**, including ambiguous-name handling,
missing values, season checks, duplicate detection, non-mutating comparison and
separation of scenarios from baseline/market values. No new historical draft
simulation was run for this task.

## Scope reset: what the previous work is for

| Work | Immediate purpose or disposition |
| --- | --- |
| League scorer and typed player inputs | Keep: convert stats into this league's points. |
| Identity/provenance checks | Keep: avoid wrong-player joins and make corrections auditable. |
| Manual draft tracker and recovery | Keep: record picks and remain usable during the actual draft. |
| Eligibility and schedule calculations | Keep: legal rosters and usable games during the season. |
| Reviewed context and starter-rate estimates | Keep as visible conditional scenarios; assess before promotion. |
| Historical replay and fixed comparison tools | Retain as validation tools, run when a concrete change warrants it. |
| Two-turn and full-draft search variants | Park as experiments; no demonstrated consistent advantage. |
| Further probability models and search infrastructure | Defer until a practical decision requires them and inputs support them. |

The experiments taught us about failure modes, but their compute cost has not
translated into a proven draft advantage. They should not receive more effort
merely because they exist. The next work should improve this visible board:
resolve the two team conflicts, prioritize missing high-market-demand projections,
review major disagreements, then use a dated eligibility/market update in a new
reviewed draft session. Streaming and weekly usable-game recommendations remain
the next major product milestone after the draft, within four weekly acquisitions
and the eventual verified waiver rules.
