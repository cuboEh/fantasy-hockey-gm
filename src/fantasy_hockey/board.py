"""An auditable historical-rate baseline and local draft-board export.

Hockey Insights provides the raw historical inputs. Its precomputed fantasy
scores and consensus ranks are intentionally not used as league projections.
"""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unicodedata

from .config import LeagueConfig
from .scoring import number, score

SOURCE = "https://hockeyinsights.ca/data/fantasy_2027.json"
FIELDS = {
    "skater": {"goals": "G", "assists": "A", "plus_minus": "PM", "power_play_points": "PPP",
               "shots_on_goal": "SOG", "hits": "HIT", "blocks": "BLK"},
    "goalie": {"wins": "W", "goals_against": "GA", "saves": "SV", "shutouts": "SO"},
}
POSITIONS = {"C": "C", "L": "LW", "R": "RW", "LW": "LW", "RW": "RW", "D": "D", "G": "G"}
SEASON_WEIGHTS = {"20252026": Decimal("0.6"), "20242025": Decimal("0.3"), "20232024": Decimal("0.1")}


def read_json(path: Path) -> dict:
    obj = json.loads(path.read_text(), parse_float=Decimal)
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected an object")
    return obj


def dump_json(value: object) -> str:
    return json.dumps(value, default=str, indent=2, sort_keys=True)


def normalized_name(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())


@dataclass(frozen=True)
class SeasonLine:
    season: str
    games: Decimal
    stats: dict[str, Decimal]


def season_lines(row: dict, kind: str, weights: dict) -> list[SeasonLine]:
    lines = []
    seen = set()
    for item in row.get("seasons", []):
        season = item.get("s")
        if season not in SEASON_WEIGHTS:
            continue
        if season in seen:
            raise ValueError(f"duplicate season {season}")
        seen.add(season)
        games = number(item.get("gp"), "games")
        if games <= 0 or games > 90:
            raise ValueError("invalid historical appearances")
        source = item.get("cats", {}) if kind == "skater" else item
        stats = {stat: number(source.get(FIELDS[kind][stat]), stat)
                 for stat, weight in weights.items() if weight != 0}
        score(kind, stats, weights)
        if kind == "goalie" and any(stats.get(s, 0) > games for s in ("wins", "shutouts")):
            raise ValueError("goalie outcomes exceed appearances")
        if kind == "skater" and all(s in stats for s in ("goals", "assists", "power_play_points")):
            if stats["power_play_points"] > stats["goals"] + stats["assists"]:
                raise ValueError("PPP exceeds goals plus assists")
        lines.append(SeasonLine(season, games, stats))
    return lines


def load_moneypuck(directory: Path | None) -> dict[str, dict]:
    if directory is None:
        return {}
    result = {}
    for kind, filename in (("skater", "skaters.csv"), ("goalie", "goalies.csv")):
        with (directory / filename).open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row.get("situation") != "all" or row.get("season") != "2025":
                    continue
                key = f"nhl:{row['playerId']}"
                if key in result:
                    raise ValueError(f"Ambiguous MoneyPuck all-situation row: {key}")
                result[key] = {"kind": kind, **row}
    return result


def annotate_moneypuck(player: dict, source: dict, lines: list[SeasonLine], mp: dict | None) -> None:
    if mp is None:
        player["flags"].append("moneypuck_unmatched")
        return
    if mp["kind"] != player["kind"] or normalized_name(mp["name"]) != normalized_name(player["name"]):
        player["flags"].append("moneypuck_identity_needs_review")
        return
    seconds = number(mp.get("icetime"), "MoneyPuck ice time")
    if seconds <= 0:
        player["flags"].append("moneypuck_no_ice_time")
        return
    if player["kind"] == "skater":
        xg = number(mp["I_F_xGoals"], "xg")
        features = {"individual_xg_per_60": xg * 3600 / seconds,
                    "goals_minus_xg": number(mp["I_F_goals"], "goals") - xg,
                    "shots_per_60": number(mp["I_F_shotsOnGoal"], "shots") * 3600 / seconds,
                    "hits_per_60": number(mp["I_F_hits"], "hits") * 3600 / seconds}
        comparisons = {"goals": "I_F_goals", "shots_on_goal": "I_F_shotsOnGoal", "hits": "I_F_hits"}
    else:
        features = {"goals_saved_above_expected": number(mp["xGoals"], "xga") - number(mp["goals"], "ga")}
        comparisons = {"goals_against": "goals"}
    latest = next((line for line in lines if line.season == "20252026"), None)
    discrepancies = {}
    if latest:
        for stat, field in comparisons.items():
            if stat in latest.stats and latest.stats[stat] != number(mp[field], field):
                discrepancies[stat] = {"hockeyinsights": latest.stats[stat], "moneypuck": number(mp[field], field)}
    if discrepancies:
        player["flags"].append("source_stat_discrepancy")
    player["analytics"] = {"source": "MoneyPuck.com", "season": "20252026",
                           "features": features, "stat_discrepancies": discrepancies,
                           "used_in_projection": False}


def build_board(path: Path, config: LeagueConfig, as_of: date,
                moneypuck_dir: Path | None = None, overrides_path: Path | None = None) -> dict:
    data = read_json(path)
    meta = data.get("meta", {})
    if meta.get("season") != "2026-27" or meta.get("seasonGames") != 84:
        raise ValueError("This adapter requires the documented 2026-27 / 84-game dataset")
    if not isinstance(meta.get("generated"), str):
        raise ValueError("Source metadata requires a generated date")
    generated = date.fromisoformat(meta["generated"])
    if generated > as_of:
        raise ValueError("Source build is after analysis date")
    overrides = read_json(overrides_path) if overrides_path else {}
    mp = load_moneypuck(moneypuck_dir)
    players = []
    seen = set()
    for group, group_kind in (("players", "skater"), ("goalies", "goalie"), ("consensusOnly", "skater")):
        for row in data.get(group, []):
            kind = "goalie" if group == "consensusOnly" and row.get("pos") == "G" else group_kind
            player_id = f"nhl:{row['id']}"
            if player_id in seen:
                raise ValueError(f"Duplicate identity: {player_id}")
            seen.add(player_id)
            position = POSITIONS.get(row.get("pos"))
            player = {"id": player_id, "external_ids": {"nhl": str(row["id"])}, "name": row["name"],
                      "kind": kind, "team": row.get("team"), "positions": [position] if position else [],
                      "position_source": "NHL primary position via Hockey Insights; Yahoo eligibility unverified",
                      "flags": list(row.get("flags", [])), "analytics": None,
                      "projected_points": None, "projected_games": None, "points_per_game": None,
                      "stats": None, "contributions": None, "adp": None}
            player["flags"].append("eligibility_unverified")
            if row.get("newTeam"):
                player["flags"].append("new_team_role_review")
                player["team_change"] = row["newTeam"]
            if row.get("roster") is False:
                player["flags"].append("not_on_source_roster")
            override = overrides.get(player_id, {})
            if override:
                allowed = {"projected_games", "positions", "team", "note", "source", "as_of"}
                if not isinstance(override, dict) or set(override) - allowed:
                    raise ValueError(f"{player_id}: unsupported override")
                if not override.get("note") or not override.get("source") or not isinstance(override.get("as_of"), str):
                    raise ValueError("Overrides require a source, note and as_of date")
                if date.fromisoformat(override["as_of"]) > as_of:
                    raise ValueError("Override evidence is after analysis date")
                if "positions" in override:
                    positions = override["positions"]
                    if not isinstance(positions, list) or not positions or any(p not in POSITIONS.values() for p in positions):
                        raise ValueError("Invalid eligibility override")
                    if (kind == "goalie") != (positions == ["G"]) or (kind == "skater" and "G" in positions):
                        raise ValueError("Eligibility conflicts with player type")
                    player["positions"] = list(dict.fromkeys(positions))
                    player["position_source"] = override["source"]
                    player["flags"].remove("eligibility_unverified")
                if "team" in override:
                    player["team"] = override["team"]
                player["override"] = override
            try:
                weights = config.weights[kind]
                lines = season_lines(row, kind, weights)
                if not lines:
                    raise ValueError("No usable historical sample; needs a separate projection")
                total_weight = sum(SEASON_WEIGHTS[line.season] for line in lines)
                rates = {stat: sum(SEASON_WEIGHTS[line.season] * line.stats[stat] / line.games for line in lines) / total_weight
                         for stat, weight in weights.items() if weight != 0}
                # Availability carry-forward, not an injury or role forecast. Historic seasons were 82 games.
                games = min(Decimal(84), sum(SEASON_WEIGHTS[line.season] * line.games for line in lines) / total_weight * 84 / 82)
                if "projected_games" in override:
                    games = number(override["projected_games"], "projected_games")
                    if not 0 <= games <= 84:
                        raise ValueError("Projected appearances must be between 0 and 84")
                if len(lines) < 3:
                    player["flags"].append("incomplete_three_season_history")
                if not any(line.season == "20252026" for line in lines):
                    player["flags"].append("no_latest_season")
                if sum(line.games for line in lines) < 60:
                    player["flags"].append("small_sample")
                if "projected_games" not in override:
                    player["flags"].append("workload_carry_forward_review")
                stats = {key: value * games for key, value in rates.items()}
                scored = score(kind, stats, weights)
                player.update({"projected_points": scored.total, "projected_games": games,
                               "points_per_game": score(kind, rates, weights).total, "stats": stats,
                               "contributions": {item.stat: item.points for item in scored.contributions},
                               "history_seasons": [line.season for line in lines]})
                if moneypuck_dir:
                    try:
                        annotate_moneypuck(player, row, lines, mp.get(player_id))
                    except (ValueError, KeyError) as exc:
                        player["flags"].append("moneypuck_annotation_unavailable")
                        player["analytics_error"] = str(exc)
            except (ValueError, KeyError) as exc:
                player["flags"].append("projection_unavailable")
                player["projection_error"] = str(exc)
                player.update({"projected_points": None, "projected_games": None, "points_per_game": None,
                               "stats": None, "contributions": None})
            players.append(player)
    if set(overrides) - seen:
        raise ValueError(f"Unknown override IDs: {', '.join(sorted(set(overrides) - seen))}")
    players.sort(key=lambda p: (p["projected_points"] is None, -(p["projected_points"] or Decimal(0)), p["id"]))
    return {"schema_version": 1, "model": "historical_rate_baseline_v1", "season": "2026-27",
            "as_of": as_of.isoformat(), "source_generated": generated.isoformat(),
            "source": SOURCE, "attribution": ["Hockey Insights (hockeyinsights.ca)"] + (["MoneyPuck.com"] if moneypuck_dir else []),
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "roster_slots": dict(config.slots), "scoring": {k:dict(v) for k,v in config.weights.items()},
            "assumptions": {"season_weights": SEASON_WEIGHTS, "season_games": 84,
                            "appearances": "weighted historical GP scaled 84/82, unless explicit override",
                            "rates": "weighted historical per-appearance rates; weights renormalized over supplied seasons"},
            "warnings": ["Unvalidated baseline, not a trained forecast or final draft recommendation",
                         "Primary NHL positions are provisional until Yahoo eligibility is verified",
                         "Pool is incomplete; rookies without history remain visible but unranked",
                         "No fitted age, injury, role or MoneyPuck adjustment; no ADP imported",
                         "Source omissions and corrections may affect historical counts",
                         f"Source build is {(as_of-generated).days} days before analysis"],
            "players": players}


def export_csv(board: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["rank", "id", "name", "team", "positions", "projected_games", "points_per_game", "projected_points", "flags", "model", "as_of", "source_generated", "source", "market_metric", "market_value", "market_source", "market_as_of", "review_note", "review_source", "review_as_of"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        rank = 0
        for player in board["players"]:
            if player["projected_points"] is not None:
                rank += 1
            row = {k: player.get(k, "") for k in fields}
            row.update({"rank": rank if player["projected_points"] is not None else "",
                        "positions": "/".join(player["positions"]), "flags": "; ".join(player["flags"]),
                        "model": board["model"], "as_of": board["as_of"], "source_generated": board["source_generated"],
                        "source": board["source"]})
            market = player.get("market") or {}
            review = player.get("review") or {}
            row.update({"market_metric":market.get("metric", ""), "market_value":market.get("value", ""),
                        "market_source":market.get("source", ""), "market_as_of":market.get("as_of", ""),
                        "review_note":review.get("note", ""), "review_source":review.get("source", ""),
                        "review_as_of":review.get("as_of", "")})
            for key in ("projected_games", "points_per_game", "projected_points"):
                row[key] = "" if player[key] is None else f"{number(player[key], key):.2f}"
            # Treat external text as text in spreadsheets, not executable formulas.
            for key, value in row.items():
                numeric_fields = {"projected_games", "points_per_game", "projected_points"}
                if key not in numeric_fields and isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                    row[key] = "'" + value
            writer.writerow(row)
