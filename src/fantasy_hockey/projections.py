"""Explicit skater role scenarios, not a fitted player-forecasting model.

Rates describe production conditional on the role and manpower situation.
Appearances and minutes describe exposure. Scenario probabilities are supplied
assumptions, never represented as calibrated confidence or outcome intervals.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from .scoring import STAT_NAMES, Score, number, score


@dataclass(frozen=True)
class Usage:
    minutes_per_appearance: Decimal
    rates_per_60: Mapping[str, Decimal]


@dataclass(frozen=True)
class RoleScenario:
    name: str
    probability: Decimal
    appearances: Decimal
    power_play: Usage
    non_power_play: Usage
    source: str
    rationale: str
    evidence_date: date
    review_date: date


@dataclass(frozen=True)
class ScenarioResult:
    scenario: RoleScenario
    stats: Mapping[str, Decimal]
    score: Score


@dataclass(frozen=True)
class Projection:
    expected_appearances: Decimal
    expected_stats: Mapping[str, Decimal]
    expected_score: Score
    scenarios: tuple[ScenarioResult, ...]
    warnings: tuple[str, ...]


def _fields(raw: object, expected: set[str], label: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError(f"{label} fields must be exactly: {', '.join(sorted(expected))}")
    return raw


def _text(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be nonempty text")
    return raw


def _nonnegative(raw: object, label: str) -> Decimal:
    result = number(raw, label)
    if result < 0:
        raise ValueError(f"{label} cannot be negative")
    return result


def _usage(raw: object, label: str) -> Usage:
    obj = _fields(raw, {"minutes_per_appearance", "rates_per_60"}, label)
    rates = obj["rates_per_60"]
    if not isinstance(rates, dict):
        raise ValueError(f"{label}.rates_per_60 must be an object")
    allowed = STAT_NAMES["skater"] - {"power_play_points"}
    if set(rates) - allowed:
        raise ValueError("Unknown rate or power_play_points provided; PPP is derived from PP goals and assists")
    normalized = {key: number(value, key) for key, value in rates.items()}
    for key, value in normalized.items():
        if value < 0 and key != "plus_minus":
            raise ValueError(f"{key} cannot be negative")
    return Usage(_nonnegative(obj["minutes_per_appearance"], label), normalized)


def parse_scenarios(raw: object) -> tuple[RoleScenario, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("scenarios must be a nonempty list")
    results = []
    required = {"name", "probability", "appearances", "power_play", "non_power_play",
                "source", "rationale", "evidence_date", "review_date"}
    for item in raw:
        obj = _fields(item, required, "Scenario")
        results.append(RoleScenario(
            _text(obj["name"], "name"),
            _nonnegative(obj["probability"], "probability"),
            _nonnegative(obj["appearances"], "appearances"),
            _usage(obj["power_play"], "power_play"),
            _usage(obj["non_power_play"], "non_power_play"),
            _text(obj["source"], "source"),
            _text(obj["rationale"], "rationale"),
            date.fromisoformat(_text(obj["evidence_date"], "evidence_date")),
            date.fromisoformat(_text(obj["review_date"], "review_date")),
        ))
    return tuple(results)


def project_roles(scenarios: tuple[RoleScenario, ...], weights: Mapping[str, object],
                  as_of: date) -> Projection:
    """Project mutually exclusive roles for one player and one common horizon.

    PP covers all power-play strengths; non-PP covers everything else. This
    avoids adding all-situation totals to overlapping power-play totals.
    """
    if not scenarios or sum((s.probability for s in scenarios), Decimal(0)) != 1:
        raise ValueError("Scenario probabilities must sum to 1")
    if len({s.name for s in scenarios}) != len(scenarios):
        raise ValueError("Scenario names must be unique")
    normalized_weights = {key: number(value, key) for key, value in weights.items()}
    if set(normalized_weights) - STAT_NAMES["skater"]:
        raise ValueError("Unsupported skater scoring weights")
    required = {key for key, weight in normalized_weights.items() if weight != 0}
    required.discard("power_play_points")
    if normalized_weights.get("power_play_points", 0) != 0:
        required |= {"goals", "assists"}
    results = []
    warnings = []
    for scenario in scenarios:
        for label, value in (("probability", scenario.probability), ("appearances", scenario.appearances)):
            _nonnegative(value, label)
        if scenario.evidence_date > as_of:
            raise ValueError(f"{scenario.name}: evidence is after the analysis date")
        if scenario.review_date < scenario.evidence_date:
            raise ValueError(f"{scenario.name}: review date precedes evidence")
        if scenario.review_date <= as_of:
            warnings.append(f"{scenario.name}: role assumption is due for review")
        totals = {key: Decimal(0) for key, weight in normalized_weights.items() if weight != 0}
        for name, usage in (("power_play", scenario.power_play), ("non_power_play", scenario.non_power_play)):
            minutes = _nonnegative(usage.minutes_per_appearance, "minutes_per_appearance")
            if minutes == 0 or scenario.appearances == 0:
                continue
            # Always require the two PP components when deriving a scored PPP.
            needed = set(required)
            if name == "non_power_play" and normalized_weights.get("power_play_points", 0) != 0:
                needed = {key for key, weight in normalized_weights.items() if weight != 0} - {"power_play_points"}
            missing = needed - set(usage.rates_per_60)
            if missing:
                raise ValueError(f"{scenario.name}/{name}: missing rates: {', '.join(sorted(missing))}")
            score("skater", usage.rates_per_60, {})  # Validate rates at the pure API boundary too.
            if "power_play_points" in usage.rates_per_60:
                raise ValueError("PPP must be derived, not supplied as an independent rate")
            exposure = scenario.appearances * minutes / Decimal(60)
            for key, rate in usage.rates_per_60.items():
                if key in totals:
                    totals[key] += number(rate, key) * exposure
            if name == "power_play" and "power_play_points" in totals:
                totals["power_play_points"] += exposure * (
                    number(usage.rates_per_60.get("goals", 0), "goals")
                    + number(usage.rates_per_60.get("assists", 0), "assists")
                )
        results.append(ScenarioResult(scenario, totals, score("skater", totals, normalized_weights)))
    expected_stats = {
        key: sum((r.scenario.probability * r.stats[key] for r in results), Decimal(0))
        for key, weight in normalized_weights.items() if weight != 0
    }
    return Projection(
        sum((s.probability * s.appearances for s in scenarios), Decimal(0)),
        expected_stats, score("skater", expected_stats, normalized_weights),
        tuple(results), tuple(warnings),
    )


def project_payload(payload: object, weights: Mapping[str, object]) -> dict:
    obj = _fields(payload, {"player_id", "horizon", "as_of", "data_type", "scenarios"}, "Role input")
    player_id = _text(obj["player_id"], "player_id")
    horizon = _text(obj["horizon"], "horizon")
    as_of = date.fromisoformat(_text(obj["as_of"], "as_of"))
    if obj["data_type"] not in ("illustrative", "analyst_scenarios"):
        raise ValueError("data_type must be illustrative or analyst_scenarios")
    projection = project_roles(parse_scenarios(obj["scenarios"]), weights, as_of)
    return {
        "player_id": player_id, "horizon": horizon, "as_of": as_of.isoformat(),
        "data_type": obj["data_type"], "model_version": "role_scenarios_v1",
        "probability_status": "supplied assumptions, not calibrated probabilities",
        "expected_appearances": str(projection.expected_appearances),
        "expected_points": str(projection.expected_score.total),
        "expected_stats": {key: str(value) for key, value in projection.expected_stats.items()},
        "contributions": {item.stat: str(item.points) for item in projection.expected_score.contributions},
        "scenario_expected_points_range": {
            "min": str(min(r.score.total for r in projection.scenarios if r.scenario.probability > 0)),
            "max": str(max(r.score.total for r in projection.scenarios if r.scenario.probability > 0)),
            "meaning": "range of positive-probability scenario means, not a prediction interval",
        },
        "scenarios": [
            {"name": r.scenario.name, "probability": str(r.scenario.probability),
             "expected_points": str(r.score.total), "source": r.scenario.source,
             "rationale": r.scenario.rationale, "evidence_date": r.scenario.evidence_date.isoformat(),
             "review_date": r.scenario.review_date.isoformat(),
             "stats": {key: str(value) for key, value in r.stats.items()}}
            for r in projection.scenarios
        ],
        "warnings": list(projection.warnings),
    }
