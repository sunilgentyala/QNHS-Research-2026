"""
Unit tests for PMA-MTJ resistance state model (QNHS Spintronic Synaptic Plane).
Validates: TMR ratio, four resistance states, switching probability model.

Run: python -m pytest tests/test_mtj_model.py -v
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from simulations.mtj_resistance_model import MTJDevice, simulate_crossbar


class TestMTJDeviceProperties(unittest.TestCase):

    def setUp(self):
        self.dev = MTJDevice(
            diameter_nm=20.0,
            tmr_ratio_pct=200.0,
            R_P_kohm=5.0,
            n_states=4,
        )

    def test_tmr_ratio_exceeds_200_pct(self):
        """TMR ratio must exceed 200% per paper Section V-B."""
        self.assertGreaterEqual(self.dev.tmr_ratio_pct, 200.0,
            msg="TMR ratio must exceed 200% as stated in paper Section V-B")

    def test_r_ap_greater_than_r_p(self):
        """Anti-parallel resistance must exceed parallel (fundamental MTJ property)."""
        self.assertGreater(self.dev.R_AP_kohm, self.dev.R_P_kohm,
            msg="R_AP must be greater than R_P")

    def test_r_ap_formula(self):
        """R_AP = R_P * (1 + TMR/100)."""
        expected = self.dev.R_P_kohm * (1 + self.dev.tmr_ratio_pct / 100.0)
        self.assertAlmostEqual(self.dev.R_AP_kohm, expected, places=10)

    def test_four_resistance_states(self):
        """Must have exactly 4 resistance states for 2-bit synaptic encoding."""
        states = self.dev.resistance_states_kohm
        self.assertEqual(len(states), 4,
            msg="Must have 4 resistance states for 2-bit per synapse encoding")

    def test_resistance_states_ordered(self):
        """Resistance states must be monotonically increasing R0 < R1 < R2 < R3."""
        states = self.dev.resistance_states_kohm
        for i in range(len(states) - 1):
            self.assertLess(states[i], states[i+1],
                msg=f"State {i} ({states[i]:.3f}) not less than state {i+1} ({states[i+1]:.3f})")

    def test_r0_equals_r_p(self):
        """R0 (fully parallel) must equal R_P."""
        states = self.dev.resistance_states_kohm
        self.assertAlmostEqual(states[0], self.dev.R_P_kohm, places=10,
            msg="R0 must equal R_P (fully parallel state)")

    def test_r3_equals_r_ap(self):
        """R3 (fully anti-parallel) must equal R_AP."""
        states = self.dev.resistance_states_kohm
        self.assertAlmostEqual(states[-1], self.dev.R_AP_kohm, places=10,
            msg="R3 must equal R_AP (fully anti-parallel state)")

    def test_read_current_positive(self):
        """Read current must be positive for all states."""
        for idx in range(self.dev.n_states):
            i_read = self.dev.read_current_nA(idx)
            self.assertGreater(i_read, 0,
                msg=f"Read current for state {idx} must be positive")

    def test_read_current_higher_for_lower_resistance(self):
        """Lower resistance state (R0) gives higher read current at same voltage."""
        i_r0 = self.dev.read_current_nA(0)
        i_r3 = self.dev.read_current_nA(3)
        self.assertGreater(i_r0, i_r3,
            msg="R0 (lowest resistance) must give highest read current")


class TestSwitchingProbability(unittest.TestCase):

    def setUp(self):
        self.dev = MTJDevice(temp_K=1.0)

    def test_zero_current_no_switch(self):
        """Zero applied current must give zero switching probability."""
        p = self.dev.switching_probability(0.0)
        self.assertAlmostEqual(p, 0.0, places=5)

    def test_above_critical_high_probability(self):
        """At or above J_c, spin-torque drives deterministic switching: p = 1.0."""
        for j_ratio in [1.0, 1.2, 1.5, 2.0]:
            p = self.dev.switching_probability(j_ratio)
            self.assertAlmostEqual(p, 1.0, places=10,
                msg=f"Deterministic switching expected at J/Jc={j_ratio}: p={p}")

    def test_probability_monotonically_increases(self):
        """Switching probability must be non-decreasing in applied current."""
        j_ratios = np.linspace(0.0, 1.5, 20)
        probs = [self.dev.switching_probability(j) for j in j_ratios]
        for i in range(len(probs) - 1):
            self.assertGreaterEqual(probs[i+1] + 1e-10, probs[i],
                msg=f"Probability not monotone at J/Jc={j_ratios[i+1]:.2f}: "
                    f"p[{i+1}]={probs[i+1]:.4f} < p[{i}]={probs[i]:.4f}")

    def test_probability_bounded(self):
        """Switching probability must be in [0, 1] for all inputs."""
        for j in np.linspace(0, 2.0, 50):
            p = self.dev.switching_probability(j)
            self.assertGreaterEqual(p, 0.0, msg=f"P < 0 at J/Jc={j}")
            self.assertLessEqual(p, 1.0 + 1e-10, msg=f"P > 1 at J/Jc={j}")

    def test_lower_temp_less_thermal_activation(self):
        """
        At sub-critical current (J < Jc), lower temperature reduces thermally
        activated switching (less thermal energy to overcome barrier).
        Cryogenic MTJ operation suppresses spurious thermal switching.
        """
        dev_1K = MTJDevice(temp_K=1.0)
        dev_300K = MTJDevice(temp_K=300.0)
        p_1K = dev_1K.switching_probability(0.5)
        p_300K = dev_300K.switching_probability(0.5)
        self.assertLess(p_1K, p_300K,
            msg="At sub-critical J, 1K device has far lower thermal activation than 300K")

    def test_switching_energy_is_01_fJ(self):
        """Switching energy stored on device must be 0.1 fJ."""
        self.assertAlmostEqual(self.dev.switching_energy_fJ, 0.1, places=10)

    def test_retention_barrier_60_kT(self):
        """Thermal stability factor Delta must be 60 k_B T (paper-consistent)."""
        self.assertAlmostEqual(self.dev.retention_barrier_kT, 60.0, places=5)


class TestCrossbarSimulation(unittest.TestCase):

    def test_crossbar_shape(self):
        """Crossbar weight matrix must have the requested shape."""
        for n in [8, 16, 32]:
            weights = simulate_crossbar(n_rows=n, n_cols=n)
            self.assertEqual(weights.shape, (n, n),
                msg=f"Expected ({n},{n}) crossbar, got {weights.shape}")

    def test_states_in_valid_range(self):
        """All crossbar state values must be in {0, 1, 2, 3}."""
        weights = simulate_crossbar(16, 16)
        for val in weights.flatten():
            self.assertIn(int(val), [0, 1, 2, 3],
                msg=f"Invalid state value {val} in crossbar")

    def test_reproducible_with_seed(self):
        """Same seed must produce identical crossbar."""
        w1 = simulate_crossbar(16, 16, seed=42)
        w2 = simulate_crossbar(16, 16, seed=42)
        np.testing.assert_array_equal(w1, w2)

    def test_different_seeds_differ(self):
        """Different seeds must produce different crossbars (with overwhelming probability)."""
        w1 = simulate_crossbar(16, 16, seed=0)
        w2 = simulate_crossbar(16, 16, seed=999)
        self.assertFalse(np.array_equal(w1, w2),
            msg="Different seeds produced identical crossbars")

    def test_256x256_crossbar_capacity(self):
        """256x256 crossbar must encode 256^2 = 65,536 synaptic connections."""
        weights = simulate_crossbar(256, 256)
        self.assertEqual(weights.size, 65536)

    def test_all_four_states_represented(self):
        """All four resistance states should appear in a 256x256 crossbar."""
        weights = simulate_crossbar(256, 256, seed=1)
        present = set(int(v) for v in weights.flatten())
        self.assertEqual(present, {0, 1, 2, 3},
            msg="Not all four resistance states represented in 256x256 crossbar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
