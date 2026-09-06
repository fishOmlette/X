import sys
import unittest
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

from coordination_simulator import (  # noqa: E402
    CoordinationConfig,
    PairHistory,
    RobotState,
    run_episode,
)


class CoordinationSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.config = CoordinationConfig(measurement_noise_s=0.0)

    def test_no_intervention_conflict_really_collides(self):
        result = run_episode(
            self.config,
            "no_intervention",
            "conflict",
            seed=1,
        )
        self.assertTrue(result["reached_goal"])
        self.assertTrue(result["collision"])
        self.assertTrue(result["headway_violation"])
        self.assertFalse(result["timed_out"])
        self.assertFalse(result["successful"])
        self.assertIsNone(result["successful_makespan_s"])

    def test_no_intervention_clear_is_successful(self):
        result = run_episode(
            self.config,
            "no_intervention",
            "clear",
            seed=1,
        )
        self.assertTrue(result["successful"])
        self.assertFalse(result["collision"])
        self.assertFalse(result["headway_violation"])
        self.assertAlmostEqual(result["makespan_s"], 20.0)

    def test_serialization_is_one_shot_and_respects_blockers(self):
        result = run_episode(
            self.config,
            "fixed_pad",
            "conflict",
            seed=1,
            parameter=4.0,
        )
        self.assertTrue(result["successful"])
        self.assertEqual(result["serialization_order"], [0, 1, 2])
        self.assertEqual(result["blockers"], [[], [0], [0, 1]])
        self.assertEqual(result["yield_events_per_robot"], [0, 1, 1])
        self.assertEqual(result["serialization_breaches"], 0)
        self.assertEqual(result["final_states"], [RobotState.CLEARED.value] * 3)

        waiting_entries = [
            (transition["robot"], transition["to"])
            for transition in result["transitions"]
            if transition["to"] == RobotState.WAITING.value
        ]
        self.assertEqual(waiting_entries, [(1, "waiting"), (2, "waiting")])

    def test_pair_histories_are_isolated_and_reset_explicitly(self):
        histories = PairHistory(window=4)
        histories.observe((0, 1), 0.0, 2.0)
        histories.observe((0, 1), 1.0, 1.0)
        histories.observe((1, 2), 0.0, 1.0)
        histories.observe((1, 2), 1.0, 2.0)
        self.assertAlmostEqual(histories.slope((0, 1)), -1.0)
        self.assertAlmostEqual(histories.slope((1, 2)), 1.0)
        self.assertEqual(histories.reset((0, 1)), 1)
        self.assertEqual(histories.slope((0, 1)), 0.0)
        self.assertAlmostEqual(histories.slope((1, 2)), 1.0)

    def test_elapsed_time_is_post_update_time(self):
        result = run_episode(
            self.config,
            "no_intervention",
            "conflict",
            seed=1,
        )
        expected = 17.5
        self.assertAlmostEqual(result["makespan_s"], expected)

    def test_invalid_method_is_rejected(self):
        with self.assertRaises(ValueError):
            run_episode(self.config, "typo", "conflict", seed=1)


if __name__ == "__main__":
    unittest.main()
