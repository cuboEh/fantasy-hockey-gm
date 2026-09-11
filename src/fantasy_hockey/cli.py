"""A small offline scoring command. Projection models and draft tracking follow."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import sqlite3

from .config import load_config
from .scoring import score
from .projections import project_payload
from . import draft_cli, preparation_cli, goalie_weeks_cli, decision_cli, market


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline fantasy hockey scoring")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("score", help="Explain the points in a normalized stat line")
    command.add_argument("--config", type=Path, required=True)
    command.add_argument("--input", type=Path, required=True)
    roles = commands.add_parser("project-roles", help="Compare explicit skater usage scenarios")
    roles.add_argument("--config", type=Path, required=True)
    roles.add_argument("--input", type=Path, required=True)
    draft_cli.register(commands)
    preparation_cli.register(commands)
    goalie_weeks_cli.register(commands)
    decision_cli.register(commands)
    market.register(commands)
    args = parser.parse_args()
    try:
        if args.command == 'compare-market':
            return market.handle(args)
        if args.command == 'draft-plan':
            return decision_cli.handle(args)
        if args.command == 'goalie-weeks':
            return goalie_weeks_cli.handle(args)
        if args.command in ('prepare-draft','draft-guide'):
            return preparation_cli.handle(args)
        if args.command in ("build-board", "draft"):
            return draft_cli.handle(args)
        config = load_config(args.config)
        raw = args.input.read_bytes()
        payload = json.loads(raw, parse_float=Decimal, object_pairs_hook=unique_object)
        if args.command == "project-roles":
            output = project_payload(payload, config.weights["skater"])
            output["input_sha256"] = hashlib.sha256(raw).hexdigest()
            output["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        if not isinstance(payload, dict):
            raise ValueError("Input must be a JSON object")
        required = {"kind", "basis", "data_type", "source", "horizon", "stats"}
        if set(payload) != required:
            raise ValueError(f"Input fields must be exactly: {', '.join(sorted(required))}")
        if payload["basis"] not in ("total", "per_game"):
            raise ValueError("basis must be total or per_game")
        if payload["data_type"] not in ("historical", "projection", "illustrative"):
            raise ValueError("data_type must be historical, projection or illustrative")
        for key in ("source", "horizon"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError(f"{key} must be a nonempty string")
        kind = payload["kind"]
        if kind not in ("skater", "goalie") or not isinstance(payload["stats"], dict):
            raise ValueError("Provide kind skater/goalie and a stats object")
        result = score(kind, payload["stats"], config.weights[kind])
        output = {key: payload[key] for key in required - {"stats"}}
        output.update({
            "total_points": str(result.total),
            "contributions": [
                {"stat": item.stat, "amount": str(item.amount), "weight": str(item.weight), "points": str(item.points)}
                for item in result.contributions
            ],
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
            "scoring_version": "0.1.0",
        })
        print(json.dumps(output, indent=2, sort_keys=True))
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"fantasy: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
