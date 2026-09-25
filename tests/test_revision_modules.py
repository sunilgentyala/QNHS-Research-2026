"""Tests for the weight-dependent STDP baselines, the shared sampling pool, the
coherent-hold analysis and the sampling/learning energy split."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulations import coherent_hold, energy_uncertainty, sampling_pool
from simulations.network_learning import NetConfig, run as net_run


class TestWeightDependentBaselines(unittest.TestCase):

    def test_new_models_learn_correlations(self):
        for m in ("mult", "vanrossum", "qstdp_huang"):
            r = net_run(m, NetConfig(T_s=40.0, g=0.2), seed=0)
            self.assertGreater(r["selectivity"], 0.05, m)
            self.assertGreater(r["updates_per_pre_spike"], 0.0)

    def test_mult_weights_stay_inside_bounds(self):
        r = net_run("mult", NetConfig(T_s=20.0, g=0.3), seed=1)
        self.assertLess(r["w_corr"], 1.0)
        self.assertGreater(r["w_uncorr"], 0.0)


class TestSamplingPool(unittest.TestCase):

    def test_erlang_c_limits(self):
        self.assertEqual(sampling_pool.erlang_c(2, 3.0), 1.0)
        self.assertAlmostEqual(sampling_pool.erlang_c(1, 0.5), 0.5, places=12)   # M/M/1: P(wait) = rho

    def test_pool_meets_target_and_is_minimal(self):
        r = sampling_pool.size_pool(64 * 64, 10.0, 2, 200e-6)
        self.assertLessEqual(r.p_wait, 0.01)
        self.assertGreater(sampling_pool.erlang_c(r.engines - 1, r.offered_load), 0.01)
        self.assertLess(r.qubits, r.dedicated_qubits)


class TestCoherentHold(unittest.TestCase):

    def test_update_is_nonlinear(self):
        self.assertGreater(coherent_hold.nonlinearity_gap(4, 0.5), 1e-4)

    def test_filter_success_matches_formula(self):
        basis = np.linspace(0, 1, 16)
        p = np.random.default_rng(2).dirichlet(np.ones(16))
        c = 0.03
        d = basis - p @ basis
        var = float(p @ d ** 2)
        s = np.max(np.abs(1 + c * d))
        self.assertAlmostEqual(coherent_hold.success_probability(p, basis, c), (1 + c * c * var) / s ** 2, places=12)

    def test_filter_gate_counts(self):
        g = coherent_hold.filter_gate_counts(4)
        self.assertEqual((g["ry"], g["cnot"], g["ancillas"]), (16, 16, 1))


class TestWorkloadEnergy(unittest.TestCase):

    def test_split_adds_up(self):
        w = energy_uncertainty.workload_point(1.5, "reprep", eps=1.0)
        f = 1 + energy_uncertainty.CARNOT
        self.assertAlmostEqual(w["wall_learn_at_1K_pJ"], (w["E_sample_fJ"] + 1.5 * w["E_learn_fJ"]) * f / 1000)
        self.assertLess(w["wall_learn_at_300K_pJ"], w["wall_learn_at_1K_pJ"])

    def test_learn_bounds(self):
        self.assertAlmostEqual(energy_uncertainty.E_LEARN_LO_FJ, 16 * (70 + 7) - 2, delta=5)


if __name__ == "__main__":
    unittest.main()
