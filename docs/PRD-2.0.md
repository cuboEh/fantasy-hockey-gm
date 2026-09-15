# Fantasy Hockey GM: PRD 2.0

**Date:** September 14, 2026
**Theme:** Dependable daily and weekly GM decisions, with model development and research
**Status:** Active. Supplied-data implementation and isolated acceptance are delivered.
Connected-read verification remains blocked by access. Daily/matchup forecast
evaluation is in progress following the September 15 raw-data audit and approved
participation-source investigation. This release is not declared complete.

The draft is complete. This contract replaces the completed
[PRD 1.1](archive/PRD-1.1.md) and its narrow roster-audit successor plan.
The user endorsed the GM direction and the expanded model/research workstream.
Unresolved input and evaluation details below must be settled before dependent
implementation or experiments; approval does not establish missing league facts.

## Scope summary

| Phase | Focus | Status |
| --- | --- | --- |
| P1 | Trustworthy league state | BLOCKED |
| P2 | Auditable forecasts, model development and bounded research | WIP |
| P3 | Roster gaps and legal lineup suggestions | Done |
| P4 | Free-agent add/drop comparisons | Done |
| P5 | Everyday browser workflow and recovery verification | Done |

Trade evaluation follows this release; automatic trade discovery follows selected
offer analysis. Direct Yahoo writes remain outside this contract.

## Product outcome

Open the app, see whether its information is current, understand today's roster
issues, and inspect a small number of legal, explained actions. The manager should
not need a terminal, several exports or a research report for routine use.

The draft's reported practical friction is evidence that passing calculation tests
and a scripted rehearsal was insufficient. On September 14 the user identified:

- Manual synchronization consumed time needed to research picks independently.
- The interface was otherwise fine, but required too much scrolling.
- Recommendations stopped after approximately "pick 12 or so."

The last report is an unresolved incident, not a diagnosed cause. The exact draft
state and whether "pick 12" means overall or personal picks remain unknown.
Before reusing the affected recommendation workflow, inspect available evidence
from an isolated copy of the completed draft and reproduce the failure if possible.
Do not alter the original session or assume absent recommendations meant there
were no useful options. The GM acceptance cases below address these failures.

## Comparison with the MVP and inspected implementation

| Capability | Original MVP 2 | Inspected foundation | Proposed direction |
| --- | --- | --- | --- |
| Roster gaps | Roster, usable games and congestion | Scoring, eligibility matching and schedule valuation | Explain empty eligible slots, stranded bench production, injury exposure and goalie qualification needs by date. Compare positional upgrades with available replacements. |
| Lineups | Obvious lineup opportunities | Daily slot matching; no complete current-roster and lock workflow | Suggest exact daily assignments and changes from the actual lineup, respecting locks and eligibility. |
| Free agents | Legal adds/drops and streams | Player forecasts and roster valuation; no verified availability/transaction workflow | Evaluate the entire resulting roster, including the drop, acquisition timing, usable games and longer-term cost. |
| Projections | Supporting inputs | Historical baselines, imported preseason projections and conditional scenarios | Dated short-term and rest-of-season forecasts with explicit workload assumptions and measured forecast errors. |
| Trades | Deferred | Reusable roster-value calculations; no trade product | First compare selected offers, then suggest a bounded set of candidates based on both rosters' needs. |
| Set lineups | Automatic actions deferred | No Yahoo writes | Manual execution in Yahoo for the next release. Direct execution remains a separate future capability. |
| Everyday usability | CLI/export considered sufficient | Local draft dashboard, persistence and stale-revision protection | Browser-first daily workflow, explicit refresh state, recovery and realistic usability acceptance. |

Code inspection is not GM acceptance evidence. In particular, the current
`RosterValue` distributes season exposure across scheduled team games, and the
goalie model uses calendar-week proxies. Neither establishes daily participation,
confirmed starters, actual matchup boundaries or lock-aware recommendations.
`LeagueConfig` currently validates scoring and slot counts, not complete transaction
rules. Existing tests exercise matching and draft stale-state behavior, not the
proposed in-season contract.

## Delivery requirements

Complete lineup and free-agent decisions before adding trade analysis or automatic
trade discovery. Existing code must be verified against this contract before it
can satisfy a requirement. Status and Notes below record actual progress.

### P1: Establish trustworthy league state

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P1-FR1 | Show the selected league/team, scoring, eligibility, roster, matchup dates, timezone, lock rules, acquisition usage, waiver timing and goalie qualification rule, with unresolved fields identified. | Done | Supplied league/team ownership and all rule fields reconcile with source; unknown assignments, usage, timezone and matchup remain explicit. Desktop and narrow browser inspected. Evidence: `tests/test_gm_settings.py`, `var/prd-2.0/p5/supplied-browser-final.json`, `p1-rules-recovery/real-league-verification.json`. |
| P1-FR2 | Show source observation time, last successful refresh, coverage and refresh errors for each decision input. | Done | Per-input observation, expiry, coverage, last successful import and refresh errors are visible; overview shows roster data age. Unknown freshness is never current. Evidence: `tests/test_gm.py`, `var/prd-2.0/p5/supplied-browser-final.json`. |
| P1-FR3 | A failed or partial refresh preserves the last complete snapshot and marks affected advice unavailable or historical. | Done | Pending/crashed, truncated, malformed, superseded and denied-read attempts retain the complete snapshot and restrict advice; successful retry recovers. Authorization failure exercised through an injected reader, not a real Yahoo session. Evidence: `tests/test_gm.py`, `tests/test_gm_decisions.py`, `var/prd-2.0/p5/browser-results.json`. |
| P1-FR4 | A roster, rule, eligibility, forecast, availability or relevant clock change invalidates affected advice. | Done | Saved decisions freeze input identity, reject stale requests before/after calculation and become historical after imports, expiry or locks. Browser lock transitions retire displayed comparisons. Evidence: `tests/test_gm_decisions.py`, `var/prd-2.0/p5/dated-browser-results.json`. |
| P1-FR5 | The manager can load and inspect a validated supplied snapshot and, when access is verified, refresh through supported Yahoo reads. | BLOCKED | Supplied-data settings/full-league/schedule normalization, import and inspection are delivered. Yahoo approval remains pending; a current supported read/authentication flow and actual league/team identity reconciliation cannot yet be verified. No Yahoo calls, scraping or writes were attempted. Provider reader boundary is tested, but is not a Yahoo adapter. |

Acceptance: reconcile an isolated snapshot with its source; exercise wrong team,
duplicate identity, unknown rule, expired authentication, interrupted/partial
refresh and a game crossing its lock time. No affected advice may appear current.
Keep credentials and league snapshots private, and external access outside scoring.

### P2: Develop and evaluate auditable forecasts

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P2-FR1 | Player views separate historical production, projected rate, expected participation and projected fantasy points for a named horizon. | Done | Player research separates historical appearances/totals, projected stat rate, dated horizon workload and projected points. Missing workload stays unknown. Evidence: `tests/test_gm_forecasts.py`, `var/prd-2.0/p5/supplied-browser-final.json`. |
| P2-FR2 | Each forecast identifies its source, issue time, assumptions and missing inputs; material changes have an inspectable explanation. | Done | Numerical contract validates source, version, issue/training/horizon dates, assumptions and missing inputs. Player details expose before/after fields since prior import. Evidence: `tests/test_gm_forecasts.py`, `tests/test_gm_decisions.py`, supplied-browser evidence. |
| P2-FR3 | Uncertain participation and goalie starts remain distinguishable from confirmed information; unsupported players remain searchable with explicit comparison limits. | Done | Confirmed, projected, scenario and unknown participation are distinct. Working advice excludes experimental/scenario forecasts; unsupported identities remain searchable. Missing goalie data preserves supported skater changes. Evidence: `tests/test_gm_forecasts.py`, `tests/test_gm_advice.py`, `var/prd-2.0/p5/browser-results.json`. |
| P2-FR4 | Save dated forecasts used in decisions and later compare workload and rate errors against a declared simple baseline. | Done | Dated reviews retain exact forecasts and inputs. Supplied-outcome evaluation reports coverage, appearance/Brier, conditional stat/rate and point errors, excluding late-frozen and duplicate cases. Real future outcome performance is not claimed. Evidence: `tests/test_gm_forecasts.py`, `tests/test_gm_decisions.py`; [guide](guides/gm-workspace.md). |
| P2-FR5 | Produce a reproducible baseline that forecasts participation and individual scoring statistics separately before applying league weights. | Done | Reproducible 730-day stat-rate baseline with 20 pooled appearance equivalents; separate Beta-smoothed workload requires an explicit eligible cohort. Same-day/future records excluded. Missing history remains unsupported. No dated external forecast was available for the comparison period. Evidence: `tests/test_gm_forecasts.py`, [research register](reference/gm-forecast-research.md). |
| P2-FR6 | Maintain a sourced research register linking each candidate signal to a forecast target or roster decision, required data, bounded experiment and accept/reject/inconclusive result. | Done | Sourced register connects user ideas to targets, required inputs and bounded decisions; first recency candidate result is recorded as rejected for general replacement. Further ideas remain a queue, not implied default adjustments. See [research register](reference/gm-forecast-research.md). |
| P2-FR7 | Evaluate baseline and candidate models on identical chronological cases and report coverage, workload error, stat/point error and uncertainty in their differences by horizon and player group. | WIP | Conditional next-game comparison is delivered. September 15 audit recovers 667,586 exposure records from 14 seasons; after the 30-game pilot, all 1,312 games of one season reconcile into 60,596 participation records. Daily/matchup evaluation still needs declared prediction-time player cohorts and separate scoring-conflict exclusions. Post-game roster reports are outcome evidence, not pregame features. See [participation audit](reference/participation-data-audit.md), tests/test_participation_records.py and tests/test_participation_pilot.py. |
| P2-FR8 | Keep experimental forecasts separate from the working model and expose the evidence and version change when a candidate is promoted or reverted. | Done | Experimental model role is explicit and excluded from working advice. The unpromoted recency version cannot be labeled working. Saved inputs and before/after model/source changes retain review/rollback evidence. No automatic promotion command exists. Evidence: `tests/test_gm_forecasts.py`, `tests/test_gm_decisions.py`. |
| P2-FR9 | Complete and document a bounded comparison of the baseline with at least one data-supported enhancement selected through the research register. | Done | One predeclared baseline/60-day recency comparison completed on 48,564 conditional-rate cases. Skater error worsened; the candidate failed the general replacement criterion and was not promoted. Includes separate listed-goalie diagnostic, coverage and limitations. Evidence: `var/prd-2.0/p2-comparison/plan.json`, `results/report.json`, `results/predictions.jsonl`. |

Acceptance: reconcile displayed points with the same underlying scoring inputs;
check missing projections, an injury scenario and unknown goalie starts. A season
total must not be counted again on top of already earned points. Conditional
scenarios must not be presented as calibrated confidence intervals.

Model acceptance: reproduce saved predictions from the same data cutoff and model
version; verify that future observations cannot enter features; distinguish missing
participation records from actual zero production. Report baseline and candidate
results on the same cases, including coverage exclusions and failed hypotheses.
Use a separate validation period for selection and an untouched test period only
after freezing the candidate. If adequate untouched history is unavailable, use
prospective shadow forecasts and leave predictive improvement unverified. FRs for
experiment delivery can be Done with a defensible negative result; a better-model
claim requires the promotion evidence.

## Model development and continued research

Run product reliability and model investigation as coordinated workstreams. P1
provides trustworthy inputs; P2 defines the shared forecast interface early so
P3-P5 can use a frozen supported model while candidate forecasts are evaluated.
Model research is explicit release work, not a promise to revisit it after the UI.
The app can ship with the strongest supported baseline if experiments do not
justify replacing it. Unfinished required experiments remain incomplete requirements.

Start from the existing [multi-source model design](reference/model-design.md), the
[product-plan ideas](product-plan.md) and archived validation evidence. The
intended calculation sequence is participation and role, predicted scoring stats,
league points, then usable roster production. Team and opponent context may affect
the first two stages; roster constraints belong in the last stage.

| Research topic | Question and proposed treatment | Priority |
| --- | --- | --- |
| Current form, ice time and PP role | Does a dated update to exposure/rates beat the frozen forecast? Test recency and shrinkage without overreacting to a short scoring streak. | First candidate group |
| Injuries, trades, linemates and role competition | Can sourced changes improve participation or deployment estimates? Keep unconfirmed changes as explicit scenarios with review dates. | First candidate group |
| Goalie workload and performance | Forecast starts, relief appearances, shot exposure and stopping performance separately; distinguish known starter information from predictions. | First candidate group |
| NHL records plus MoneyPuck features | Does xG, shot quality, assist composition or goalie context improve the corresponding future stats beyond the same raw-stat baseline? | First candidate group |
| Age, experience and sparse history | Can position/role priors improve estimates for developing players and players with little NHL history? Track those groups separately. | After baseline coverage audit |
| Opponent strength and easier/harder stretches | Does an as-of-date opponent adjustment improve per-game forecasts beyond player/team role and schedule volume? | User idea, explicit research queue |
| Repeated opponents and player-versus-team history | Does matchup history add predictive information after sample size, opponent quality, deployment and team changes are accounted for? | User idea, exploratory until tested |
| Off nights and fantasy playoff schedules | Which extra games fit the actual roster and verified playoff dates? Schedule fit is a calculation; any opponent-strength forecast needs separate validation. | Core usable-game work plus user research idea |
| NHL team concentration, stacks and goalie tandems | Does shared scheduling or joint outcome uncertainty change roster decisions? Existing matching handles collisions; any additional correlation effect needs separate evidence. | User idea, later decision experiment |
| External projections or model blends | Does a permitted dated forecast or validation-selected blend beat each component alone on comparable coverage? | Benchmark first, blend only with evidence |

This queue captures previously recorded ideas; it does not imply that every signal
must become a default adjustment or that every experiment must finish in 2.0.
P2-FR9 requires one bounded enhancement comparison. Further completed experiments
are selected by a named decision and data readiness, not by preferred player names.

For each investigation, record the hypothesis, primary/official methodology sources
and dates, usable data permissions and timestamps, baseline, forecast horizon,
chronological partitions, main metric, subgroup checks, finite run budget and
stopping rule. Literature can justify testing an idea; it cannot establish that
our implementation improves this league's predictions. Log all tried candidates
so repeated model selection is visible. A new trial needs a new question or evidence.

Proposed evaluation measures, to finalize before experiments: absolute error for
appearances, scoring stats and fantasy points; Brier score and calibration for
participation probabilities; empirical coverage and width for any prediction
intervals. Report skaters and goalies separately and retain workload-versus-rate
breakdowns. Compare uncertainty in model differences across dates/weeks, accounting
for repeated players and shared games rather than treating every row as independent.

Test decision usefulness separately: replay the same starting rosters and legal
action opportunities using each forecast and a competent simple policy. A replay
needs dated eligibility, availability, locks and outcomes; missing historical league
state limits the claim to a labeled diagnostic. Keep forecast improvements distinct
from a policy improvement or a projected gain generated by the model itself.

Continue after launch with dated shadow predictions, a proposed weekly error/data
review and a monthly candidate-model review. Those are human review cadences, not
an unattended schedule created by this PRD. Use errors to prioritize research;
do not retune after each loss or repeatedly inspect a reserved test set. Retain the
current working version and a reproducible rollback path throughout.

### P3: Explain gaps and suggest lineups

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P3-FR1 | Show today's and the current matchup's scheduled games, assignable games, projected usable production and bench congestion by date. | Done | Date plans report remaining scheduled/assignable games, usable points and benched opportunities; started games are excluded from future totals. Explicit schedule coverage required. Evidence: `tests/test_gm_advice.py`, `var/prd-2.0/p5/dated-browser-results.json`. |
| P3-FR2 | Suggest exact eligible assignments and changes from the observed lineup while preserving locked players and respecting active, bench and injury-slot rules. | Done | Exact complete-roster assignment respects eligibility, active/bench capacity, locked starters/bench and held injury slots. Unknown assignments or unsupported constraints restrict affected plans. Evidence: collision, lock, injury, vacancy and started-candidate cases in `tests/test_gm_advice.py`. |
| P3-FR3 | Explain each roster gap using dates, affected slots and production or qualification consequences. | Done | Gap explanations identify dates, open positions, absent/started/unsupported games and projected benched production. Goalie qualification has a separate exposure alternative and point cost. Evidence: `tests/test_gm_advice.py`, `var/prd-2.0/p5/layout-and-errors.json`. |
| P3-FR4 | Separate confirmed qualifying goalie appearances already earned from future conditional opportunity within actual matchup boundaries. | Done | Confirmed supplied qualification results count only within actual matchup boundaries; future appearances remain conditional. Unknown qualification and negative exposure are visible. Evidence: partial-matchup and goalie-alternative cases in `tests/test_gm_advice.py`. |
| P3-FR5 | Compare lineup advice with the actual lineup and a simple legal points-first lineup on the same roster and horizon. | Done | The suggestion uses the exact legal points-first baseline, with today's observed-lineup total and changes shown separately. Choosing the same assignments is allowed; no novelty objective. Evidence: hand-calculated collision/lock/negative cases and no-change browser revision in `var/prd-2.0/p5/browser-results.json`. |

Acceptance: hand-check a multi-position collision, a locked player, an injury-slot
restriction, a timezone boundary and a partially completed matchup. Verify negative
goalie-point exposure and any qualification tradeoff are explicit. Missing goalie
inputs must not prevent supported skater advice.

### P4: Recommend bounded free-agent opportunities

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P4-FR1 | Distinguish free agents, pending waivers and owned players using dated availability information. | Done | Owned/free-agent/waiver/unknown states retained and cross-checked against supplied ownership. Passed clearance times require refreshed availability. Evidence: `tests/test_gm_settings.py`, `tests/test_gm_advice.py`. |
| P4-FR2 | Compare a legal single add/drop or add into a vacant roster place against keeping the current roster with the same lineup management. | Done | Single current free-agent add/drop or vacant regular/injury add checks acquisitions, supported processing, locks, drop permission and full resulting capacity. Pending waivers remain restricted with clearance shown. Evidence: `tests/test_gm_advice.py` and browser comparisons. |
| P4-FR3 | Show added and lost usable production, the exact player dropped, transaction cost, goalie impact and separate rest-of-season opportunity cost. | Done | Full-roster net change, candidate usable points, drop loss, acquisition cost and goalie impact shown. Separate ROS comparison needs explicit season end and coverage; unknown cost prevents a drop recommendation. Positive short-term/negative ROS case keeps roster. Evidence: `tests/test_gm_advice.py`. |
| P4-FR4 | Permit a manager-selected candidate and a keep-roster result; explain exclusions and assumptions. | Done | Browser supports manager-selected candidates/drop and no-drop vacancies. Restricted reasons and keep-roster results are visible. Three usable games beat four colliding games in a hand-checked case. Evidence: `tests/test_gm_advice.py`, `var/prd-2.0/p5/browser-results.json`. |

Acceptance: a four-game pickup whose games collide must not automatically outrank
a three-game usable pickup. Exercise a strong incumbent, no acquisitions left,
waiver clearance after the useful game, a vacant roster place, unknown availability
and a move whose short-term gain sacrifices long-term value. Compare the full
resulting roster; do not add raw player points to a separate schedule bonus.

### P5: Verify the everyday experience

| FR | Requirement | Status | Notes |
| --- | --- | --- | --- |
| P5-FR1 | From the browser, the manager can refresh/import, review today's issues, inspect a lineup and compare a pickup without terminal commands. | Done | Supplied-data browser loop covers import/refresh, daily plans, player evidence and pickup comparison without terminal use during review. Connected source acquisition remains P1-FR5. Evidence: `var/prd-2.0/p5/browser-results.json`, `dated-browser-results.json`. |
| P5-FR2 | Advice visibly identifies action, reason, expected benefit, cost, uncertainty and data age, with detailed evidence available on demand. | Done | Overview and expanded results show action/restriction, projected gain, full-roster costs, uncertainty, qualification tradeoff and data age. Historical stats and projections remain separate. Evidence: `var/prd-2.0/p5/layout-and-errors.json`, `supplied-browser-final.json`. |
| P5-FR3 | Reopening restores the last valid context and locally saved comparisons; failed refresh and restart have a verified recovery path. | Done | Local research context survives page reload; SQLite retains dated reviews and comparisons. Interrupted import/restart renews session token and recovers with last snapshot intact. Evidence: `tests/test_gm_decisions.py`, `var/prd-2.0/p1-rules-recovery/browser-verification.json`, `p5/browser-results.json`. |
| P5-FR4 | After manual execution in Yahoo, a subsequent verified import/read reconciles the actual state and retires obsolete advice. | Done | A supplied post-action ownership/assignment import replaces the roster and retires prior advice. Local review saves never assert a Yahoo action occurred. Tested with explicit simulated post-action inputs, not live Yahoo writes. Evidence: `tests/test_gm_decisions.py`, `var/prd-2.0/p5/dated-practices.json`. |
| P5-FR5 | A bounded isolated browser rehearsal verifies the daily loop and failure recovery on desktop and narrow screens against declared usability and response-time targets. | Done | Isolated desktop/narrow rehearsal and three consecutive explicitly simulated dates pass. On the recorded machine, 18-player/512-catalog overview and comparison meet 2s/5s targets; browser review finishes within 5 minutes. This is not three actual days of manager use. Evidence: `var/prd-2.0/p5/performance.json`, `dated-browser-results.json`, `layout-and-errors.json`. |
| P5-FR6 | Refreshing or importing a complete snapshot updates roster and availability without individual transaction re-entry and preserves the selected research view. | Done | Twenty browser import/recalculation cycles retain research filter and selected player, including partial inputs and recovery. Reload restores context; removed or newly owned selections remain explained. Evidence: `var/prd-2.0/p5/browser-results.json`, supplied-browser checks. |
| P5-FR7 | The desktop overview shows data freshness, priority issues and the leading supported action or its absence reason within the first viewport; player details return to the same list position. | Done | Desktop overview shows data age and leading action/restriction above fold. Narrow navigation reaches player/pickup views without horizontal overflow. Back-to-results retains position. Evidence: `var/prd-2.0/p5/layout-and-errors.json`, `supplied-browser-final.json`. |
| P5-FR8 | Every recommendation request ends in supported advice, an explained no-change result, an explicit input restriction, or a visible error with a retry/recovery path. | Done | Requests terminate in supported/partial advice, keep-roster, restriction or visible retryable error. Injected calculation failure preserves research and recovers; stale comparisons are retired. Evidence: `tests/test_gm_decisions.py`, `var/prd-2.0/p5/layout-and-errors.json`, `browser-results.json`. |

Acceptance: run one scripted failure rehearsal and three consecutive dated practice
reviews, including changed availability and a lock transition. Each critical result
must reconcile with the source snapshot. Stop after checks pass; repeat only for
changes or unresolved failures. Run required unit tests for scoring changes and
observe changed browser interactions. Record evidence in each FR's Notes.

Add a bounded sequence of 20 roster/availability revisions and recalculations in an
isolated GM session, crossing the reported approximate failure count. Include a
full roster, constrained candidate pool, unsupported player, empty valid shortlist,
calculation failure and subsequent valid recovery. Verify displayed state after
each revision. This is a GM continuity check, not proof that the draft incident has
been reproduced or diagnosed. Verify that refreshing during player research
preserves context and supersedes stale advice, and inspect P5-FR7's viewports.

## Trade roadmap

After the daily loop is dependable, deliver selected-offer analysis, then bounded
trade suggestions. For each side compare usable rest-of-season production before
and after, positional fit, schedule congestion and uncertainty. Multi-player deals
must account for forced drops and the value of filling a freed roster place.
Use the same horizons and assumptions for both sides. Include keeping the roster
and available free-agent alternatives.

A suggested partner needs verified league-wide rosters. Complementary roster needs
can explain why an offer might interest both managers; our projection advantage is
not an acceptance probability or proof of a fair market price. Start with selected
one-for-one offers, then bounded one-for-one discovery. Defer package search until
replacement and roster-capacity handling pass explicit acceptance cases.

## Direct lineup setting and API access

Yahoo's current [access application](https://sports.yahoo.com/developer/access/)
states that access is read-only and write access is unavailable (search result
checked September 14, 2026; direct page fetch was rate-limited). Older
[API documentation](https://sports.yahoo.com/developer/docs/) describes read/write
operations; that does not establish available write permission for this app.
Repository instructions also prohibit roster writes and Yahoo scraping/browser
automation. The next PRD therefore produces suggestions for manual execution.

If supported writes become available and the user changes that boundary, define a
separate execution contract: preview, explicit authorization, immediate state/lock
recheck, duplicate prevention, server read-back and handling of partial failures.
Do not promise reversal after a lineup locks or a player is dropped.

## Input and evaluation decisions before dependent work

Updated settings were supplied directly by the user on September 14 and recorded
in ignored private configuration with the prior version preserved. They supersede
the earlier private settings for GM work. Do not infer actual league participation
from the maximum-team setting, or league timezone from the displayed draft time.
The supplied playoff week labels still require actual matchup date boundaries.
P1 now carries supplied rule fields through normalization and retains unfamiliar
fields explicitly. Preserving a rule does not establish executable semantics.
Do not reuse draft-era goalie thresholds, injury slots or playoff assumptions as
GM defaults. Receiving settings does not verify the current roster, transaction
usage, waiver priority or Yahoo connection.

1. Draft friction is recorded above and mapped to P5-FR6 through P5-FR8. Investigate
   the recommendation incident using isolated evidence before reusing the affected
   workflow; do not invent a cause if evidence is insufficient.
2. Yahoo approval is confirmed pending by the user on September 14. Validate a real
   read once access is granted. Until then, this can be an import-based preview;
   connected everyday readiness remains explicitly undelivered.
3. Selected-offer trade evaluation follows 2.0, with automatic trade discovery
   later. Any change to that boundary requires an explicit scope revision.
4. Resolve input freshness limits, exact league rules, a sustainable dated forecast
   source/update policy before dependent implementation. Record the reference
   environment for P5 response-time targets; finalize P2 evaluation thresholds
   and data partitions before experiments.

## Supplied-data delivery checkpoint

The implementation now includes statistical forecasts, immutable dated reviews,
conditional workload handling, exact lineup assignments, gap explanations and
single pickup comparisons. All supported-input behavior is verified independently
of the original draft recommender. The full test suite and browser evidence are
under `var/prd-2.0/p5/`; private league inputs remain ignored and source files
unchanged. The existing draft recommendation incident remains undiagnosed and its
workflow was not reused.

P1-FR5 remains blocked on approved and verified supported Yahoo reads. P2-FR7 was
reopened on September 15: missing normalized fields did not establish that raw
participation data was unavailable. Its audit and source pilot now support further
data engineering. Daily/matchup evaluation remains unfinished; conditional
next-game results do not fill that gap. The
current real workspace also needs verified timezone/matchup dates, actual lineup
assignments, current transaction/availability and participation information before
its plans can be considered actionable. Those values are not inferred from the
completed draft. The user has been asked only for these missing current fields,
not to resend the league rosters.

The connected release and predictive performance are not certified. Do not mark
these gates complete using mock authentication, simulated practice dates or
historical rates alone. Approved reads, participation-data reconciliation and dated
observation collection are the next steps. The September 15 user authorization
covers the data audit and proposed source expansion, not a new parameter search.
