"""Read explicit local league settings without embedding private defaults."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import tomllib

from .scoring import STAT_NAMES, number


@dataclass(frozen=True)
class LeagueConfig:
    scoring_type: str
    slots: Mapping[str, int]
    weights: Mapping[str, Mapping[str, Decimal]]


def load_config(path: Path) -> LeagueConfig:
    with path.open("rb") as stream:
        raw = tomllib.load(stream, parse_float=Decimal)
    league = raw.get("league", {})
    if not isinstance(league, dict) or league.get("scoring_type") != "h2h_points":
        raise ValueError("Only explicit league.scoring_type = 'h2h_points' is supported")
    slots = raw.get("roster", {})
    allowed = {"C", "LW", "RW", "D", "G", "BN", "IR", "IR+"}
    if not isinstance(slots, dict) or not slots or set(slots) - allowed:
        raise ValueError("roster must contain supported position counts")
    if any(type(count) is not int or count < 0 for count in slots.values()):
        raise ValueError("Roster counts must be nonnegative integers")
    if not any(slots.get(key, 0) > 0 for key in {"C", "LW", "RW", "D", "G"}):
        raise ValueError("Roster must have at least one active slot")
    scoring = raw.get("scoring")
    if not isinstance(scoring, dict) or set(scoring) != set(STAT_NAMES):
        raise ValueError("Provide scoring.skater and scoring.goalie tables")
    weights = {}
    for kind, known in STAT_NAMES.items():
        source = scoring[kind]
        if not isinstance(source, dict) or not source or set(source) - known:
            raise ValueError(f"Invalid or unsupported {kind} scoring weights")
        weights[kind] = MappingProxyType({key: number(value, key) for key, value in source.items()})
    return LeagueConfig("h2h_points", MappingProxyType(slots), MappingProxyType(weights))
