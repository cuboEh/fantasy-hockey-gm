# GM workspace

PRD 2.0 provides a separate local GM workspace with supplied league imports,
dated statistical forecasts, lineup plans, roster-gap explanations and single
pickup comparisons. Yahoo read approval remains pending. Current real-league
recommendations require verified current inputs; completed-draft ownership alone
does not establish lineup assignments or free-agent availability.

## Open a workspace

```sh
uv run fantasy gm init --db var/gm-practice.sqlite \
  --league-id demo-league --team-id demo-team
uv run fantasy gm dashboard --db var/gm-practice.sqlite --port 8766 --open
```

`init` refuses overwrites. Reopen an existing workspace with `dashboard`. These
commands reject draft databases. Keep real snapshots and databases in ignored
`var/` or `snapshots/`. The [basic example](../reference/gm-snapshot.example.json)
contains fictional inputs and deliberately missing forecasts. Its fixed dates
will appear expired when inspected later. The numerical acceptance fixture is
`decision_snapshot` in `tests/test_gm_advice.py`; it is fictional, never live advice.

## Daily browser workflow

1. **Import snapshot** replaces all supplied inputs together. **Refresh view** reads
   the local database; it does not contact Yahoo. Read the freshness and leading
   action or restriction at the top before using a result.
2. **Lineups** shows remaining scheduled and usable games by date, exact assignments,
   changes from today's observed lineup and benched production. Expand the gap
   explanations or stat/workload evidence when needed. Started games are held and
   excluded from future point totals.
3. Review goalie qualification separately. Confirmed earned appearances and future
   expectations are distinct. The points-first plan can bench a negative goalie;
   a separate maximum-exposure alternative shows the projected point cost. Neither
   expected appearances nor that alternative guarantees meeting the minimum.
4. **Players** searches the supplied inventory, including unsupported players.
   **Inspect** separates historical totals, projected rate, horizon workload and
   points. It shows source, model role, issue time, assumptions, missing inputs and
   before/after forecast changes. **Back to results** restores the list position.
5. **Pickups** compares one selected candidate and drop, or a vacant roster place,
   against keeping the roster. It values the full resulting roster. A short-term
   gain without supported rest-of-season cost remains a review, not a drop
   recommendation. Pending waivers show their clearance time and remain restricted
   until availability is confirmed. No waiver success is assumed.
6. **Save dated review** and pickup comparisons preserve their exact input snapshot
   locally. Later imports or time boundaries label saved results historical. After
   a manual Yahoo move, import verified ownership and assignments to reconcile it.
   Saving a review does not establish that Yahoo executed anything.

Searches, the selected player and candidate/drop preferences survive imports and
page reloads in local browser storage. If that storage is unavailable, inspection
still works. Failed calculations show a visible retry path while research remains
available. The app rereads state every ten seconds and at known clock boundaries.

## Normalize existing supplied data

```sh
uv run fantasy gm settings --config config.local.toml \
  --output var/gm-settings.json --source user-supplied \
  --observed-at '<source timestamp with timezone>'
uv run fantasy gm prepare-league --input var/league-analysis/snapshot.json \
  --settings var/gm-settings.json --league-id local-league \
  --source supplied-completed-draft --observed-at '<source timestamp with timezone>' \
  --output var/gm-league.json
```

Both commands refuse output overwrites. The league normalizer reuses the saved
full draft, checks contiguous picks and complete per-team roster capacity, and
preserves all team ownership and the player inventory. Local team IDs have the
form `local-league:seat:N`; they are not Yahoo IDs. Inspect those IDs, initialize
a separate workspace with them, then import:

```sh
uv run fantasy gm import --db var/gm.sqlite --input var/gm-league.json
uv run fantasy gm show --db var/gm.sqlite
uv run fantasy gm show --db var/gm.sqlite --as-of 2026-09-14T18:00:00Z
```

The selected identity is fixed at initialization. Undrafted players remain
availability unknown. Active/bench/injury assignments and subsequent transactions
are not inferred. Settings retain extended rules and unfamiliar fields; preserving
a field does not establish executable semantics. Maximum team capacity is separate
from actual participation. Display date labels do not establish league timezone
or Yahoo matchup boundaries.

## Dated forecasts and evaluation

```sh
uv run fantasy gm forecast --input var/gm-league.json \
  --history var/history-2024.json var/history-2025.json var/history-2026.json \
  --issued-at '<issue timestamp with timezone>' --horizon-end '<end timestamp>' \
  --source 'Saved history with recorded provenance' --output var/gm-forecast.json
uv run fantasy gm evaluate --db var/gm.sqlite \
  --outcomes var/observed-outcomes.json --output var/forecast-evaluation.json
```

The working baseline uses individual scoring-stat rates with a pooled prior.
The [research register](../reference/gm-forecast-research.md) defines the formula,
coverage and completed comparison. The recency candidate remains experimental;
`--model gm-rates-recency-1` cannot silently promote it into lineup advice.

`--participation` accepts a JSON mapping of player ID to game ID to a dated object:
`observed_at`, `expected_appearances` (0 through 1), `participation` (`confirmed`,
`projected` or `scenario`) and `basis`. Confirmed values must be 0 or 1. Without
this evidence, participation remains unknown. Alternatively provide `observed_at`
and `eligible_history` with explicit dated `appeared` booleans; this estimates a
Beta-smoothed cohort probability. Establish that eligible cohort separately.
Missing observations are not absence labels. Scenario workload is inspectable but
excluded from working lineup advice.

Forecast outputs refuse overwrites and start with unknown freshness. Establish a
source-specific expiry before using them as current decision inputs. A snapshot
of old forecasts must not be made current merely by importing it again. The saved
NHL schedule can be normalized with `gm_settings.schedule_components`; this reuses
its original observation timestamp and leaves freshness unknown.

Outcomes are a JSON list with `player_id`, `game_id`, `starts_at`, `observed_at`,
explicit boolean `appeared` and a complete scoring-stat mapping `stats`. Evaluation
uses the earliest saved pre-game forecast per model/player/game. Missing outcomes
remain missing. It reports coverage and separate workload, conditional-rate and
point errors; it does not promote models or establish a fair paired comparison
when model coverage differs.

## Snapshot contract, version 1

The root contains exactly `schema_version`, `data_type`, `league`, `team`, `inputs`.
`data_type` is `illustrative` or `user_supplied`. League and team objects each have
an `id` matching the initialized workspace and a display `name`.

The six original input envelopes are required: `settings`, `roster`, `availability`,
`schedule`, `player_status`, `forecasts`. Optional envelopes are `league_rosters`,
`players`, `schedule_coverage` and `goalie_results`. Every envelope has:

| Field | Meaning |
| --- | --- |
| `source` | Supplied provenance, not authenticated verification. |
| `observed_at` | ISO timestamp with timezone, no later than import time. |
| `expires_at` | Later freshness deadline, or null for unknown. No provider SLA is inferred. |
| `coverage` | `complete` for the stated inventory, or `missing`. |
| `reason` | Nonempty missing-input explanation, otherwise null. |
| `data` | Component data, or null for missing inputs. |

Missing envelopes have null observation, expiry and data. Record counts do not
establish a complete player universe. `schedule_coverage` explicitly identifies
`start`, `end` (exclusive) and covered NHL `teams`; this is required for lineup
valuation. Settings need actual inclusive matchup dates and an IANA timezone.

Roster and player rows contain `id`, `name`, `nhl_team`, `positions` and
`selected_position`. Optional `can_drop` and `injury_slots` record verified drop
permission and eligible injury slots. Null remains unknown. Active, bench and
injury capacities must fit. Injury players are held in their supplied slots;
unsupported eligibility is explained. A direct injury add requires verified
eligibility, a vacant injury slot and an explicit enabling league rule.

Availability states are `owned`, `free_agent`, `waivers` and `unknown`, with
`owner_team_id` and optional `waiver_clears_at`. Supplied selected-roster and
league-wide ownership must agree. A passed waiver deadline never becomes a free
agent automatically. Unsupported processing rules restrict the affected move.

Schedule rows contain `id`, two `teams` and timezone-aware `starts_at`. Status rows
contain `id`, `status`, `confirmed`. Current confirmed unavailability conflicting
with a forecast restricts that player. Unknown goalie inputs do not prevent
supported skater changes. Goalie results contain distinct `id`, `player_id`,
`game_id`, explicit `qualified` and `confirmed: true`; already-started schedule and
observation dates must reconcile. These are supplied league qualification results,
not inferred starts or NHL appearances.

Legacy forecast inventories remain readable. Numerical rows additionally require
`kind`, `source`, `model_role`, `training_end`, `history`, `rates`, `games`,
`assumptions`, `missing_inputs`. Their issue and horizon fields remain required.
Each game names its schedule ID/start, expected appearances, participation status
and basis. History is explicitly historical and reconciles with the scoring weights;
it is never added to future projected points. A supplied `league_details.season_end`
and complete schedule/forecast coverage enable a separate rest-of-season usable
comparison. Its horizon overlaps the matchup and must not be added to matchup gain.

## Recovery and current limits

Imports are complete replacements, with durable attempts recorded before reads.
Malformed, partial, older or inconsistent imports preserve the last valid snapshot
and make advice unavailable. Previously supplied components cannot be silently
discarded. A crash leaves an unfinished marker across restart; a successful complete
import recovers. An older concurrent attempt cannot overwrite newer state.
Refreshing an already open page after restart renews its local session token.

Decision identities include inputs, import revision and clock boundaries. A stale
request is rejected before saving, and checked again after calculation. Saved
reviews remain inspectable as historical evidence after invalidation.

Connected Yahoo reads, provider authentication and a real-team daily rehearsal
remain unverified while access and current inputs are unavailable. No Yahoo
scraping, browser workaround or roster writes are implemented. The independent
offline rehearsal uses fictional inputs and explicitly simulated dates; it is not
three days of actual manager use or proof of predictive improvement.
