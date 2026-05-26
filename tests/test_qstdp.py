"""
Unit tests for Quantum Spike-Timing-Dependent Plasticity (Q-STDP) simulation.
Validates Eq. (2): alpha_l^(t+1) = N[ alpha_l + eta * K(dt) * alpha_l ]

Run: python -m pytest tests/test_qstdp.py -v
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from simulations.qstdp_simulation import QSTDPSynapse, simulate_qstdp_learning


class TestQSTDPSynapseInit(unittest.TestCase):

    def test_amplitude_norm_unity(self):
        """Initial amplitude vector must be normalized: sum |alpha_l|^2 = 1."""
        for k in [1, 2, 4, 8]:
            syn = QSTDPSynapse(k=k, seed=0)
            norm_sq = np.sum(np.abs(syn.alpha) ** 2)
            self.assertAlmostEqual(norm_sq, 1.0, places=12,
                msg=f"k={k}: amplitude vector not normalized, ||alpha||^2 = {norm_sq}")

    def test_hilbert_space_dimension(self):
        """Number of basis states must be 2^k."""
        for k in [1, 2, 3, 4]:
            syn = QSTDPSynapse(k=k)
            self.assertEqual(len(syn.alpha), 2**k,
                msg=f"k={k}: expected {2**k} states, got {len(syn.alpha)}")

    def test_weight_basis_range(self):
        """Weight basis states must span [0, 1]."""
        syn = QSTDPSynapse(k=4)
        self.assertAlmostEqual(float(syn.weight_basis[0]), 0.0, places=10)
        self.assertAlmostEqual(float(syn.weight_basis[-1]), 1.0, places=10)
        self.assertEqual(len(syn.weight_basis), 16)


class TestSTDPKernel(unittest.TestCase):

    def setUp(self):
        self.syn = QSTDPSynapse(A_plus=0.2, A_minus=0.21, tau_plus_ms=20.0, tau_minus_ms=20.0)

    def test_ltp_positive(self):
        """K(dt > 0) must be positive (LTP: post fires after pre)."""
        for dt in [1.0, 5.0, 20.0, 50.0]:
            k = self.syn.stdp_kernel(dt)
            self.assertGreater(k, 0, msg=f"K({dt}) should be positive for dt>0")

    def test_ltd_negative(self):
        """K(dt < 0) must be negative (LTD: post fires before pre)."""
        for dt in [-1.0, -5.0, -20.0, -50.0]:
            k = self.syn.stdp_kernel(dt)
            self.assertLess(k, 0, msg=f"K({dt}) should be negative for dt<0")

    def test_zero_dt(self):
        """K(0) must be zero by definition."""
        self.assertEqual(self.syn.stdp_kernel(0.0), 0.0)

    def test_exponential_decay_ltp(self):
        """LTP kernel must decay: |K(dt1)| > |K(dt2)| for 0 < dt1 < dt2."""
        k1 = self.syn.stdp_kernel(5.0)
        k2 = self.syn.stdp_kernel(50.0)
        self.assertGreater(k1, k2, msg="LTP kernel must decay with increasing dt")

    def test_exponential_decay_ltd(self):
        """LTD kernel must decay: |K(dt1)| > |K(dt2)| for dt1 > dt2 (more negative)."""
        k1 = abs(self.syn.stdp_kernel(-5.0))
        k2 = abs(self.syn.stdp_kernel(-50.0))
        self.assertGreater(k1, k2, msg="LTD kernel must decay with increasing |dt|")

    def test_kernel_bounded(self):
        """Kernel magnitude must be bounded by A_plus or A_minus."""
        for dt in np.linspace(-100, 100, 200):
            k = self.syn.stdp_kernel(dt)
            self.assertLessEqual(abs(k), max(self.syn.A_plus, self.syn.A_minus) + 1e-10)


class TestQSTDPUpdate(unittest.TestCase):

    def test_norm_preserved_after_update(self):
        """Amplitude vector must remain normalized after each Q-STDP update."""
        syn = QSTDPSynapse(k=4, seed=42)
        for dt in [10.0, -5.0, 30.0, -20.0, 1.0]:
            syn.update(dt)
            norm_sq = np.sum(np.abs(syn.alpha) ** 2)
            self.assertAlmostEqual(norm_sq, 1.0, places=10,
                msg=f"Norm not preserved after update with dt={dt}")

    def test_ltp_shifts_mass_to_higher_weights(self):
        """Sustained LTP (dt > 0) must increase mean weight over time."""
        syn = QSTDPSynapse(k=4, seed=7)
        initial_mean = syn.mean_weight()
        for _ in range(200):
            syn.update(dt_ms=15.0)  # sustained potentiation
        final_mean = syn.mean_weight()
        self.assertGreater(final_mean, initial_mean,
            msg="Sustained LTP should increase mean weight")

    def test_ltd_shifts_mass_to_lower_weights(self):
        """Sustained LTD (dt < 0) must decrease mean weight over time."""
        syn = QSTDPSynapse(k=4, seed=7)
        initial_mean = syn.mean_weight()
        for _ in range(200):
            syn.update(dt_ms=-15.0)  # sustained depression
        final_mean = syn.mean_weight()
        self.assertLess(final_mean, initial_mean,
            msg="Sustained LTD should decrease mean weight")

    def test_mean_weight_in_range(self):
        """Mean weight must stay in [0, 1] at all times."""
        syn = QSTDPSynapse(k=4, seed=0)
        for dt in np.random.default_rng(0).uniform(-50, 50, 500):
            syn.update(dt)
            mean = syn.mean_weight()
            self.assertGreaterEqual(mean, 0.0, msg=f"Mean weight {mean} < 0")
            self.assertLessEqual(mean, 1.0, msg=f"Mean weight {mean} > 1")

    def test_entropy_is_nonnegative(self):
        """Shannon entropy of weight distribution must be >= 0."""
        syn = QSTDPSynapse(k=4, seed=1)
        for dt in [10.0, -5.0, 20.0]:
            syn.update(dt)
            h = syn.weight_entropy()
            self.assertGreaterEqual(h, 0.0, msg=f"Entropy {h} < 0")

    def test_max_entropy_uniform(self):
        """Uniform distribution should give maximum entropy = log2(2^k) = k bits."""
        k = 4
        syn = QSTDPSynapse(k=k)
        n = 2**k
        syn.alpha = np.ones(n, dtype=complex) / np.sqrt(n)
        expected_max = float(k)
        self.assertAlmostEqual(syn.weight_entropy(), expected_max, places=10,
            msg="Uniform distribution must yield maximum entropy = k bits")

    def test_sample_weight_in_basis(self):
        """Sampled weight must be one of the basis states."""
        syn = QSTDPSynapse(k=4, seed=99)
        for _ in range(50):
            w = syn.sample_weight()
            self.assertIn(round(w, 10),
                [round(b, 10) for b in syn.weight_basis],
                msg=f"Sampled weight {w} not in basis")


class TestQSTDPSimulation(unittest.TestCase):

    def test_simulation_runs(self):
        results = simulate_qstdp_learning(n_events=100, k=4)
        self.assertEqual(len(results["mean_weights"]), 100)
        self.assertEqual(len(results["entropies"]), 100)

    def test_final_probs_sum_to_one(self):
        results = simulate_qstdp_learning(n_events=200, k=4)
        total = np.sum(results["final_probs"])
        self.assertAlmostEqual(total, 1.0, places=10,
            msg="Final probability distribution must sum to 1")

    def test_entropies_nonnegative(self):
        results = simulate_qstdp_learning(n_events=100, k=4)
        for i, h in enumerate(results["entropies"]):
            self.assertGreaterEqual(h, 0.0, msg=f"Entropy at step {i} is negative: {h}")

    def test_k_controls_basis_size(self):
        for k in [2, 3, 4]:
            results = simulate_qstdp_learning(n_events=10, k=k)
            self.assertEqual(len(results["final_probs"]), 2**k)
            self.assertEqual(len(results["weight_basis"]), 2**k)

    def test_representational_capacity(self):
        """
        256x256 crossbar with k=4 must yield 10^6 complex d.o.f. (Eq. 4 in paper).
        D = 256^2 * 2^4 = 65536 * 16 = 1,048,576 ~ 10^6
        """
        n_synapses = 256 * 256
        k = 4
        d_qnhs = n_synapses * (2**k)
        self.assertGreater(d_qnhs, 1e6, msg="D_QNHS must exceed 10^6 complex d.o.f.")
        self.assertAlmostEqual(d_qnhs, 1048576, places=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
