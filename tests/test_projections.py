from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from fantasy_hockey.projections import project_payload

ROOT = Path(__file__).resolve().parents[1]


class RoleProjectionTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT / "examples/roles.json").read_text(), parse_float=Decimal)
        self.weights = {"goals": 5, "assists": 3, "power_play_points": 1}

    def test_exposure_and_ppp_bonus_without_double_counting(self):
        payload = deepcopy(self.payload)
        payload["scenarios"] = payload["scenarios"][:1]
        payload["scenarios"][0]["probability"] = 1
        result = project_payload(payload, self.weights)
        # 75*(15/60*1 + 3/60*2) = 26.25 goals, not an all-situation plus PP sum.
        self.assertEqual(Decimal(result["expected_stats"]["goals"]), Decimal("26.25"))
        self.assertEqual(Decimal(result["expected_stats"]["assists"]), Decimal("39.375"))
        self.assertEqual(Decimal(result["expected_stats"]["power_play_points"]), Decimal("18.75"))
        self.assertEqual(Decimal(result["expected_points"]), Decimal("268.125"))
        self.assertNotIn("blocks", result["expected_stats"])

    def test_weighted_scenarios(self):
        result = project_payload(self.payload, self.weights)
        self.assertEqual(Decimal(result["expected_points"]), Decimal("232.125"))
        self.assertEqual(Decimal(result["expected_stats"]["power_play_points"]), Decimal("11.25"))
        self.assertEqual(Decimal(result["expected_appearances"]), 75)
        self.assertIn("not a prediction interval", result["scenario_expected_points_range"]["meaning"])

    def test_reducing_appearances_reduces_all_production(self):
        original = project_payload(self.payload, self.weights)
        for scenario in self.payload["scenarios"]:
            scenario["appearances"] = Decimal("37.5")
        result = project_payload(self.payload, self.weights)
        self.assertEqual(Decimal(result["expected_points"])*2, Decimal(original["expected_points"]))

    def test_probability_and_identity_validation(self):
        for value in (Decimal("0.3"), -1, "NaN", True):
            payload = deepcopy(self.payload)
            payload["scenarios"][0]["probability"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                project_payload(payload, self.weights)
        self.payload["scenarios"][1]["name"] = self.payload["scenarios"][0]["name"]
        with self.assertRaisesRegex(ValueError, "unique"):
            project_payload(self.payload, self.weights)

    def test_missing_required_rate_and_ppp_override_rejected(self):
        for situation in ("power_play", "non_power_play"):
            payload = deepcopy(self.payload)
            del payload["scenarios"][0][situation]["rates_per_60"]["goals"]
            with self.subTest(situation=situation), self.assertRaisesRegex(ValueError, "missing rates"):
                project_payload(payload, self.weights)
        self.payload["scenarios"][0]["power_play"]["rates_per_60"]["power_play_points"] = 5
        with self.assertRaisesRegex(ValueError, "PPP is derived"):
            project_payload(self.payload, self.weights)

    def test_ppp_only_scoring_requires_goals_and_assists_on_pp(self):
        for scenario in self.payload["scenarios"]:
            scenario["non_power_play"]["rates_per_60"] = {}
        result = project_payload(self.payload, {"power_play_points": 1})
        self.assertEqual(Decimal(result["expected_points"]), Decimal("11.25"))
        self.assertEqual(set(result["expected_stats"]), {"power_play_points"})

    def test_zero_exposure_and_negative_plus_minus(self):
        for scenario in self.payload["scenarios"]:
            scenario["power_play"] = {"minutes_per_appearance": 0, "rates_per_60": {}}
        result = project_payload(self.payload, {"plus_minus": 1, "power_play_points": 1})
        self.assertEqual(Decimal(result["expected_points"]), Decimal("-3.75"))
        self.assertEqual(Decimal(result["expected_stats"]["power_play_points"]), 0)

    def test_evidence_dates_and_review_warning(self):
        self.payload["scenarios"][0]["evidence_date"] = "2026-09-11"
        with self.assertRaisesRegex(ValueError, "after the analysis"):
            project_payload(self.payload, self.weights)
        self.payload["scenarios"][0]["evidence_date"] = "2026-09-10"
        self.payload["as_of"] = "2026-09-14"
        result = project_payload(self.payload, self.weights)
        self.assertEqual(len(result["warnings"]), 2)

    def test_cli_and_malformed_input(self):
        cmd = [sys.executable, "-m", "fantasy_hockey.cli", "project-roles", "--config",
               str(ROOT / "config.example.toml"), "--input"]
        run = subprocess.run(cmd + [str(ROOT / "examples/roles.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["data_type"], "illustrative")
        self.assertEqual(len(result["input_sha256"]), 64)
        self.assertEqual(result["model_version"], "role_scenarios_v1")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            payload = deepcopy(self.payload)
            payload["scenarios"][0]["power_play"]["minutes_per_appearance"] = None
            path.write_text(json.dumps(payload, default=str))
            bad = subprocess.run(cmd + [str(path)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertNotIn("Traceback", bad.stderr)
            self.assertEqual(bad.stdout, "")


if __name__ == "__main__":
    unittest.main()
