from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from fantasy_hockey.config import load_config
from fantasy_hockey.scoring import score

ROOT = Path(__file__).resolve().parents[1]


class ScoringTests(unittest.TestCase):
    def test_power_play_points_stack_and_plus_minus_is_signed(self):
        result = score("skater", {"goals": 1, "power_play_points": 1, "plus_minus": -2},
                       {"goals": 5, "power_play_points": 1, "plus_minus": 1})
        self.assertEqual(result.total, Decimal(4))
        self.assertEqual(sum(x.points for x in result.contributions), result.total)

    def test_goalie_win_shutout_and_saves_stack(self):
        result = score("goalie", {"wins": 1, "shutouts": 1, "saves": 30, "goals_against": 0},
                       {"wins": 4, "shutouts": 3, "saves": "0.2", "goals_against": -2})
        self.assertEqual(result.total, Decimal(13))

    def test_goalie_can_produce_negative_points(self):
        result = score("goalie", {"goals_against": 5, "saves": 10},
                       {"goals_against": -2, "saves": "0.2"})
        self.assertEqual(result.total, Decimal(-8))

    def test_fractional_projections_preserve_precision(self):
        self.assertEqual(score("skater", {"goals": "0.3"}, {"goals": "0.1"}).total, Decimal("0.03"))

    def test_missing_is_not_zero(self):
        with self.assertRaisesRegex(ValueError, "Missing scored statistics"):
            score("skater", {"goals": 1}, {"goals": 5, "hits": 1})

    def test_zero_weight_does_not_require_stat(self):
        self.assertEqual(score("skater", {"goals": 1}, {"goals": 5, "hits": 0}).total, 5)

    def test_unweighted_stat_does_not_change_score(self):
        self.assertEqual(score("skater", {"goals": 1, "blocks": 9}, {"goals": 5}).total, 5)

    def test_reject_bad_values_and_wrong_stat_names(self):
        for value in (None, True, "", "NaN", "Infinity", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                score("skater", {"goals": value}, {"goals": 5})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            score("skater", {"goal": 1}, {"goals": 5})
        with self.assertRaises(ValueError):
            score("skater", {"goals": 1}, {"goals": "NaN"})

    def test_example_configuration(self):
        config = load_config(ROOT / "config.example.toml")
        self.assertEqual(config.weights["skater"]["shots_on_goal"], Decimal("0.5"))
        with self.assertRaises(TypeError):
            config.slots["C"] = 99

    def test_bad_configuration_is_rejected(self):
        original = (ROOT / "config.example.toml").read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            for text in (original.replace('h2h_points', 'h2h_categories'),
                         original.replace('C = 1', 'C = -1'),
                         original.replace('goals = 5', 'goal = 5')):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_cli_reports_provenance_and_fails_cleanly(self):
        cmd = [sys.executable, "-m", "fantasy_hockey.cli", "score", "--config", str(ROOT / "config.example.toml"), "--input"]
        run = subprocess.run(cmd + [str(ROOT / "examples/skater.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        output = json.loads(run.stdout)
        self.assertEqual(Decimal(output["total_points"]), Decimal("10.5"))
        self.assertEqual(output["data_type"], "illustrative")
        self.assertEqual(len(output["config_sha256"]), 64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"kind":"skater","kind":"goalie"}')
            failed = subprocess.run(cmd + [str(path)], capture_output=True, text=True)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertIn("Duplicate JSON key", failed.stderr)


if __name__ == "__main__":
    unittest.main()
