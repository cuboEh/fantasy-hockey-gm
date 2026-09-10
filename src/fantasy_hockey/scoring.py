"""Provider-independent points scoring, with an auditable contribution breakdown."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

STAT_NAMES = {
    "skater": frozenset({"goals", "assists", "plus_minus", "power_play_points", "shots_on_goal", "hits", "blocks"}),
    "goalie": frozenset({"wins", "goals_against", "saves", "shutouts"}),
}


def number(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label}: expected a finite number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label}: expected a finite number") from exc
    if not result.is_finite():
        raise ValueError(f"{label}: expected a finite number")
    return result


@dataclass(frozen=True)
class Contribution:
    stat: str
    amount: Decimal
    weight: Decimal
    points: Decimal


@dataclass(frozen=True)
class Score:
    total: Decimal
    contributions: tuple[Contribution, ...]


def score(kind: str, stats: Mapping[str, object], weights: Mapping[str, object]) -> Score:
    """Score totals OR per-game rates. Caller must keep the input basis consistent.

    Every nonzero weighted statistic is required. Unweighted known stats have
    no direct value. Unknown stat names fail, rather than hiding spelling errors.
    """
    if kind not in STAT_NAMES:
        raise ValueError("kind must be skater or goalie")
    unknown = (set(stats) | set(weights)) - STAT_NAMES[kind]
    if unknown:
        raise ValueError(f"Unsupported {kind} statistics: {', '.join(sorted(unknown))}")
    values = {key: number(value, key) for key, value in stats.items()}
    for key, value in values.items():
        if value < 0 and key != "plus_minus":
            raise ValueError(f"{key}: cannot be negative")
    normalized = {key: number(value, f"weight {key}") for key, value in weights.items()}
    missing = [key for key, weight in normalized.items() if weight != 0 and key not in values]
    if missing:
        raise ValueError(f"Missing scored statistics: {', '.join(sorted(missing))}")
    contributions = tuple(
        Contribution(key, values[key], weight, values[key] * weight)
        for key, weight in sorted(normalized.items())
        if key in values
    )
    return Score(sum((item.points for item in contributions), Decimal(0)), contributions)
