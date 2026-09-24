"""Tests for the extended analysis modules (re-preparation noise, network
learning, energy uncertainty, poisoning, MTJ TRNG)."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulations import energy_uncertainty, mtj_trng, poisoning
from simulations.network_learning import NetConfig, run as net_run
from simulations.reprep_noise import (NoiseModel, gate_counts, mean_weight, random_targets,
                                      simulate_distribution, state_prep_circuit, tvd, _depolarize,
                                      _dephase_all, _embed, X, Y, Z)


class TestStatePrepCircuit(unittest.TestCase):

    def test_ideal_circuit_is_exact(self):
        for k in (1, 2, 3, 4):
            for p in random_targets(k, 5, seed=3):
                self.assertLess(tvd(p, simulate_distribution(p, NoiseModel.ideal())), 1e-9)

    def test_gate_counts(self):
        for k in (2, 3, 4):
            n_ry, n_cx = gate_counts(state_prep_circuit(random_targets(k, 1)[0]))
            self.assertEqual(n_ry, 2 ** k - 1)
            self.assertEqual(n_cx, 2 ** k - 2)

    def test_output_is_distribution(self):
        q = simulate_distribution(random_targets(4, 1)[0], NoiseModel.hot_qubit())
        self.assertAlmostEqual(q.sum(), 1.0, places=9)
        self.assertTrue(np.all(q >= 0))


class TestNoiseChannels(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(1)
        A = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
        self.rho = A @ A.conj().T
        self.rho /= np.trace(self.rho)

    def test_depolarize_matches_pauli_form(self):
        for q in range(3):
            Xq, Yq, Zq = _embed(X, q, 3), _embed(Y, q, 3), _embed(Z, q, 3)
            ref = 0.9 * self.rho + 0.1 / 3 * (Xq @ self.rho @ Xq + Yq @ self.rho @ Yq.conj().T + Zq @ self.rho @ Zq)
            self.assertTrue(np.allclose(_depolarize(self.rho, [q], 0.1, 3), ref))

    def test_dephasing_matches_phase_flip_form(self):
        p = 0.5 * (1 - np.exp(-0.3))
        ref = self.rho
        for q in range(3):
            Zq = _embed(Z, q, 3)
            ref = (1 - p) * ref + p * (Zq @ ref @ Zq)
        self.assertTrue(np.allclose(_dephase_all(self.rho, 300.0, 1000.0, 3), ref))

    def test_benchmark_mapping_reproduces_average_fidelity(self):
        from simulations.reprep_noise import _depolarize
        nm = NoiseModel.from_benchmarks(0.99, 0.99, readout=0.0)
        bell = np.zeros(4); bell[0] = bell[3] = 1 / np.sqrt(2)
        rho = _depolarize(np.outer(bell, bell), [1], nm.p1, 2)
        f_pro = float(bell @ rho @ bell)
        self.assertAlmostEqual((2 * f_pro + 1) / 3, 0.99, places=10)

    def test_more_noise_more_error(self):
        p = random_targets(4, 1, seed=7)[0]
        e_mk = tvd(p, simulate_distribution(p, NoiseModel.millikelvin()))
        e_hot = tvd(p, simulate_distribution(p, NoiseModel.hot_qubit()))
        self.assertGreater(e_hot, e_mk)


class TestNetworkLearning(unittest.TestCase):

    def test_classical_stdp_selects_correlated_inputs(self):
        r = net_run("classical", NetConfig(T_s=100.0, g=0.2), seed=0)
        self.assertGreater(r["selectivity"], 0.2)

    def test_qstdp_selects_correlated_inputs(self):
        r = net_run("qstdp_ideal", NetConfig(T_s=100.0, g=0.2), seed=0)
        self.assertGreater(r["selectivity"], 0.1)


class TestEnergyUncertainty(unittest.TestCase):

    def test_efficiency_dominates(self):
        r = energy_uncertainty.sample(n=20_000, mode="hold")
        rho = r["spearman_vs_ratio"]
        self.assertEqual(max(rho, key=lambda k: abs(rho[k])), "eps")

    def test_reprep_drive_time_counts_cnot_duration(self):
        # 15 rotations x 33 ns + 14 CNOTs x 100 ns for k = 4
        self.assertAlmostEqual(energy_uncertainty.drive_time_s("reprep", 4), 1.895e-6, places=12)
        self.assertAlmostEqual(energy_uncertainty.drive_time_s("hold"), 33e-9, places=15)

    def test_point_energies(self):
        self.assertAlmostEqual(energy_uncertainty.point_energy_fJ("hold"), 11.09, places=6)
        self.assertAlmostEqual(energy_uncertainty.point_energy_fJ("reprep"), 66.95, places=6)

    def test_reprep_costs_more(self):
        h = energy_uncertainty.sample(n=20_000, mode="hold")
        p = energy_uncertainty.sample(n=20_000, mode="reprep")
        self.assertGreater(p["e_syn_fJ_median"], h["e_syn_fJ_median"])


class TestPoisoning(unittest.TestCase):

    def test_attack_raises_weight(self):
        clean = np.mean([poisoning.run(0.0, 1000, seed=s) for s in range(5)])
        attacked = np.mean([poisoning.run(0.1, 1000, seed=s) for s in range(5)])
        self.assertGreater(attacked - clean, 0.1)

    def test_detection_false_positive_rate_bounded(self):
        self.assertLessEqual(poisoning.detection_power(0.0, window=200, trials=20000), 0.012)

    def test_detection_power_grows_with_attack(self):
        self.assertGreater(poisoning.detection_power(0.2), poisoning.detection_power(0.05))


class TestMTJTRNG(unittest.TestCase):

    def test_window_narrows_when_cold(self):
        self.assertLess(mtj_trng.window(1.0)["window_rel"], mtj_trng.window(300.0)["window_rel"] / 10)

    def test_j50_gives_half(self):
        w = mtj_trng.window(300.0)
        self.assertAlmostEqual(mtj_trng.p_switch(w["J50_over_Jc"], 300.0), 0.5, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
