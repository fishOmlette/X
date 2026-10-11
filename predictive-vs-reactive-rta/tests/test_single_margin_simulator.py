import sys
import unittest
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

from single_margin_simulator import (
    Cfg,
    conservative_crossing_zone_stopping_deadline,
    replay_last_collision_avoiding_trigger,
    run_episode,
)


class SingleMarginSimulatorTests(unittest.TestCase):
    def test_episode_is_deterministic_for_seed(self):
        arguments = dict(
            cfg=Cfg(),
            method="P",
            severity=6.0,
            condition="conflict",
            seed=1234,
            horizon=1.75,
            degradation_exponent=1.4,
        )
        self.assertEqual(run_episode(**arguments), run_episode(**arguments))

    def test_elapsed_time_counts_completed_updates(self):
        one_step = Cfg(x0_A=-0.05, goal_A=0.05, y0_B=-9.0)
        result = run_episode(one_step, "B0", 0.0, "clear", 0)
        self.assertTrue(result["reached_goal"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["steps_executed"], 1)
        self.assertAlmostEqual(result["elapsed_time"], one_step.dt)

        timeout = Cfg(T_max=0.3, goal_A=100.0)
        result = run_episode(timeout, "B0", 0.0, "clear", 0)
        self.assertFalse(result["reached_goal"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["steps_executed"], 3)
        self.assertAlmostEqual(result["elapsed_time"], 3 * timeout.dt)

    def test_invalid_method_is_rejected_before_simulation(self):
        with self.assertRaisesRegex(ValueError, "unknown method"):
            run_episode(Cfg(), "not-a-method", 1.0, "conflict", 0)

    def test_deadlines_are_honest_and_respond_to_braking(self):
        cfg = Cfg()
        analytical = conservative_crossing_zone_stopping_deadline(cfg)
        expected = (-cfg.x_zone - cfg.x0_A - cfg.v_nom**2 / (2 * cfg.a_max)) / cfg.v_nom
        self.assertAlmostEqual(analytical, expected)

        weaker = conservative_crossing_zone_stopping_deadline(Cfg(a_max=0.5))
        stronger = conservative_crossing_zone_stopping_deadline(Cfg(a_max=2.0))
        self.assertLess(weaker, analytical)
        self.assertGreater(stronger, analytical)

        replay = replay_last_collision_avoiding_trigger(cfg, "conflict")
        self.assertIsNotNone(replay)
        self.assertAlmostEqual(replay / cfg.dt, round(replay / cfg.dt))
        self.assertLessEqual(replay, -cfg.y0_B / cfg.vB_conflict)


if __name__ == "__main__":
    unittest.main()
