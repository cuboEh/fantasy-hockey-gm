# Strategy review before further model development

Researched September 11, 2026. Model development is paused for this review.
No rankings, forecasts, draft picks, or selection rules changed.

The working hypothesis should be a league-specific, skater-led value strategy
with price-sensitive goalie acquisition and active roster management. That is a
proposal to evaluate, not an established winner. Neither a fixed positional order
nor our recent goalie-coverage objective has earned default status through evidence.

## Evidence and its limits

Yahoo Help is the authority for platform behavior. Analyst articles supply
strategic arguments, not controlled proof. Provider methodology explains what a
stat measures, not whether it improves our fantasy decisions. Reddit discussions
were useful for finding competing hypotheses, but anecdotal league wins and
unspecified scoring systems were not treated as validation.

Some Yahoo Help pages could not be fetched directly; their relevant text was
available through indexed results from the official pages. No authenticated league
settings were inspected. Older strategy articles below inform principles, not
current player rankings or current positional depth.

## 1. Start with the scoring format

Yahoo distinguishes cumulative weekly fantasy-point scoring from category
contests. Our supplied league settings describe H2H points. There is no independent
win for shots, hits or goalie statistics. Improving a weak stat matters through
its point contribution, not because we need a balanced category profile.
[Yahoo H2H scoring](https://help.yahoo.com/kb/SLN6212.html).

Our own arithmetic illustrates why generic rankings can mislead:

- 100 additional shots contribute 90 FP; 100 additional hits contribute 100 FP.
- Blocks and faceoff wins have no direct value under the supplied weights.
- A power-play goal earns the goal, power-play-point and shot contributions.
- A 30-save, three-goal-against win earns 14 FP before any other applicable stats;
  a 20-save, two-goal-against win earns 11. More saves can offset worse goals against.
- Turning a save into a goal allowed on the same shot changes those contributions
  by -3.6 FP, before any effect on the win or shutout.

These are scoring examples, not player projections. Plus/minus also has a sizable
weight here, so team context deserves attention without treating past plus/minus
as a certain repeat. No claim about its predictive reliability was established
by this review.

## 2. Scarcity means comparing alternatives, not awarding a position bonus

Dobber's positional-scarcity discussion argues that wings can be harder to replace
than centers and that defensive production can fall sharply below the elite tier.
It is a 2019 salary-cap column, so its player examples and exact conclusions do
not establish today's depth in this league.
[Dobber positional scarcity](https://dobberhockey.com/2019/03/14/capped-positional-scarcity-and-buysell/).

Our inference: calculate a current league-scored distribution by Yahoo eligibility
and compare the best option now with plausible later options. A superstar center
can remain the right first pick even if ordinary centers are plentiful. A winger
should not receive an arbitrary premium simply for being a winger.

With the supplied 14-team configuration, active-slot demand is 28 C, 28 LW, 28 RW,
56 D and 28 G, before benches. Those counts help define demand; they do not prove
how many productive players are available. Multi-position eligibility couples
those pools, so independently ranking a dual-eligible player twice overstates
supply. Four defense slots make the elite-D question worth testing, but do not
justify automatically taking a defenseman in a specified round.

Compare overall pick numbers, not round advice copied from a 10-team league.
Actual Yahoo ranks and eligibility remain essential. The current partial market
proxy does not establish which current players our friends will overlook.

## 3. Goalie timing: credible late-goalie argument, conditional execution

Yahoo analyst Ben Zweiman's February 24, 2026 article advocates spending premium
capital on skaters and taking several later goalie opportunities, supported by
examples of disappointing expensive goalies and productive cheaper options.
That is relevant contemporary analyst opinion, but it is an in-season argument,
not a multi-year controlled test under our weights, roster size and transaction
limit. Its suggestion of three or four late goalies carries bench costs here.
[Yahoo's late-goalie argument](https://sports.yahoo.com/fantasy/article/fantasy-hockey-its-time-to-stop-investing-so-heavily-in-goaltending-163716252.html).

An older Yahoo strategy article recommends waiting within a goalie tier and
reacting as that tier depletes. This provides a useful competing principle:
remaining alternatives and price matter more than an absolute ban on early
picks. It does not supply valid current tiers.
[Yahoo goalie-tier strategy](https://sports.yahoo.com/yahoo-fantasy-hockey-secret-to-drafting-nhl-goalies-142242489.html).

Proposed interpretation: distinguish elite-goalie spending from sufficient goalie
coverage. Test delaying expensive goalies while protecting access to plausible
workloads. Also test one discounted established option plus later upside. In a
14-team league, a large share of useful goalies may be rostered, so cheap waiver
starts cannot be assumed. Avoid trading one unsupported certainty, elite goalie
projections, for another, endless usable goalie streams.

## 4. A platform-rule uncertainty is resolved

Yahoo Help says the minimum counts appearances in active goalie positions and
includes a goalie who enters the game. Missing the minimum removes goalie point
production. This supports the penalty concept in our experiments and corrects
my earlier suggestion that its application to points leagues was still entirely
unverified. The supplied minimum is three; account-specific settings and matchup
dates still need to be inspected when access is available.
[Yahoo minimum goalie appearances](https://help.yahoo.com/kb/SLN6878.html).

Our current projection uses starts as its exposure. Relief appearances therefore
remain a missing source of qualification and production. We should model them
separately, not multiply starter scoring rates by all appearances. The historical
replay already tracks appeared records, creating a projection/replay distinction
that must remain visible. Relief alone has not been shown to explain the model's
large coverage errors.

## 5. Draft a roster that can be managed

Daily Faceoff's streaming analysis explicitly combines quieter game nights,
limited transactions and available goalie opportunities. Its December 2023
examples are historical illustrations, not current pickup recommendations.
[Daily Faceoff streaming approach](https://www.dailyfaceoff.com/news/fantasy-hockey-weekend-streaming-targets-week-9).

Yahoo's Daily-Today setting makes roster changes effective immediately, while
player lineup locks still depend on game time. An immediate transaction does not
make a player whose game has started retrospectively usable.
[Yahoo transaction and lineup deadlines](https://help.yahoo.com/kb/fantasy-hockey/sln6775.html).

Our inference for an active manager: retaining some roster flexibility can be more
valuable than holding a marginal season-long bench player. Four weekly acquisitions
must be shared among injuries, skater streams and goalie coverage. One add can
produce several useful games; four adds do not mean four extra games. An off-night
helps only if the acquired player can occupy an otherwise useful active slot.
Do not add a separate schedule bonus after already crediting those usable games.

The latest draft comparisons excluded streaming. They can compare unmanaged
rosters, but cannot establish the best draft strategy for Tristan's intended
management style. A late-goalie strategy must face the same waiver competition,
processing delays, transaction cap and information limits as every other strategy.
The waiver type and waiting period remain unknown; evaluate explicit scenarios
rather than pretending there are always instantly available free agents.

## 6. Research inputs should improve projections, not become extra fantasy points

MoneyPuck distinguishes shot-quality expectations, shooting talent and goalie
performance. Its glossary defines expected save percentage relative to shot
quality; it is not a promised future save percentage.
[MoneyPuck glossary](https://www.moneypuck.com/glossary.htm).
Its methodology also describes multi-season goalie information and contextual
inputs for likely starters, making workload and talent separate modeling tasks.
[MoneyPuck methodology](https://www.moneypuck.com/about.htm).

Our proposed use is to help estimate scored outcomes and confidence: shot volume,
finishing, deployment, saves and goals against. Do not add GSAx, xG or a site rating
as a second reward on top of the fantasy production it helped predict. Record the
provider/model vintage because retrospective revisions can invalidate a purported
as-of backtest. Published methodology is not permission to bulk collect a site;
use documented downloads or explicitly permitted exports.

Daily Faceoff documents a customizable rankings workflow with selectable stats.
That makes a provider baseline worth investigating before constructing more
forecasts from scratch. This review did not buy access, obtain a projection export,
or verify a current bulk-use license.
[Daily Faceoff customization guide](https://www.dailyfaceoff.com/news/how-to-using-the-fantasy-hockey-customizable-rankings-tool).

## Implications for our existing model

Keep the scoring engine, identity separation, usable-lineup calculations, audit
traces, independent opponent preferences, and frozen prospective forecasts.
Do not equate reduced goalie failures with a better draft. Do not interpret our
57.15% synthetic all-play result as a chance of beating real opponents. Current
context coverage and actual Yahoo market knowledge remain incomplete.

The missing comparison is a set of recognizable manager strategies, evaluated
with the same forecasts and the same realistic management opportunities:

| Candidate | Question it tests |
| --- | --- |
| League-scored best available | What does a straightforward competent manager achieve? |
| Existing coverage | Does explicit goalie insurance justify its pick cost? |
| Skater-first, delayed goalies | Does early skater investment beat expensive goalie coverage? |
| One goalie anchor plus later value | Does a mixed approach reduce late-goalie availability risk? |
| Positional-tier value | Can measurable winger/D drop-offs improve choices without rigid position order? |

These are proposed benchmark families, not new implementations or fixed round
prescriptions. Declare their thresholds and exceptions before running them, and
avoid choosing them to exclude specific historical busts. A second comparison
should give every policy the same active-management rules. Report points, weekly
all-play results, missed minimums, acquisition use and between-season variability.
Actual matchup or playoff win claims need an explicit matchup simulation.

## Recommended order after this review

1. Finalize this strategy specification before changing algorithms. Use skater-led,
   tier-aware, price-sensitive drafting as a hypothesis, not a hard-coded winner.
2. Obtain current Yahoo eligibility/ranks and an independent permitted preseason
   projection baseline. Show missing coverage and disagreement explicitly.
3. Create league-specific tiers and later-pick alternatives. Audit high-impact
   workloads and roles; keep health assumptions separate from reported facts.
4. Compare the manager-style baselines, first with identical fixed management,
   then with the same legal streaming policy. Include multiple seats and uncertain
   opponent preferences. Resolve or vary unknown waiver assumptions.
5. Only then decide whether more sophisticated search adds enough value to justify
   its complexity. Preserve the existing prospective snapshot throughout.

Research conclusion: the original slot-value objective remains sound. The order
of development drifted toward optimizing a narrow goalie failure before we had
established the right draft and management benchmarks. This review resets that
order without claiming that an article has solved the league.


## Yahoo draft-analysis source supplied by Tristan

[Yahoo draft analysis](https://hockey.fantasysports.yahoo.com/hockey/draftanalysis)
was supplied September 11 as a candidate draft-market source. Direct access from
the research browser returned HTTP 429; current standard-draft rows, season and
filters were not verified or imported. A search result exposed a salary-cap
variant, which must not be substituted for snake-draft ADP.

Next: inspect a user-supplied copy of the standard-draft table, including column
headers and any season/format filters. Preserve average pick, Yahoo rank, position
and percent drafted as separate fields wherever actually supplied. ADP describes
market behavior; it does not establish value under this league's scoring or a
calibrated probability of surviving until the next pick. No automated collection
or ranking changes were made.


### User-supplied table received

Three pasted batches now supply 210 unique player names, retained under
`snapshots/2026-09-11/yahoo-user-supplied/`. The cumulative file is
`draft-analysis-first-210.json`; earlier versions are preserved. Team/position
strings, integer rank, percent drafted, two decimal strings and extra status
tokens are staged without changing live data. Column alignment and season remain
unconfirmed. Decimal averages alone must not define opponent ordering, especially
where drafted percentages differ sharply. Exact normalized-name comparison is
only a candidate identity match; unmatched names and eligibility differences are
recorded in `comparison-first-210.json`.
