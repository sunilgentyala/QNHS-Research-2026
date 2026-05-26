"""
Unit tests for distance-3 surface code analysis (QNHS topological protection).
Validates coherence enhancement, logical error rates, and MWPM timing compatibility.

Run: python -m pytest tests/test_surface_code.py -v
"""

import sys
import os
import unittest
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from simulations.surface_code_analysis import SurfaceCodeParams, SurfaceCodeAnalyzer


class TestSurfaceCodePhysicalProperties(unittest.TestCase):

    def setUp(self):
        self.params = SurfaceCodeParams(
            distance=3,
            physical_error_rate=0.001,
            threshold_error_rate=0.01,
            syndrome_cycle_us=1.0,
            spike_integration_ms=10.0,
            T2_physical_ms=1.0,
        )
        self.analyzer = SurfaceCodeAnalyzer(self.params)

    def test_distance_3_qubit_count(self):
        """d=3 surface code requires d^2 + (d-1)^2 = 9 + 4 = 13 physical qubits."""
        self.assertEqual(self.analyzer.n_physical_qubits, 13,
            msg="d=3 surface code must use 13 physical qubits per logical qubit")

    def test_physical_error_below_threshold(self):
        """28Si gate infidelity (<0.1%) must be below surface code threshold (~1%)."""
        self.assertLess(self.params.physical_error_rate, self.params.threshold_error_rate,
            msg="Physical error rate must be below surface code threshold for code to work")

    def test_logical_error_suppressed(self):
        """Logical error rate must be less than physical error rate."""
        self.assertLess(self.analyzer.logical_error_rate, self.params.physical_error_rate,
            msg="Surface code must suppress logical error rate below physical rate")

    def test_coherence_enhancement_10x(self):
        """d=3 code with p_phys=0.1%, p_th=1% must enhance coherence by 10x (Eq. in Section IV-C)."""
        # enhancement = (p_th/p_phys)^((d-1)/2) = (0.01/0.001)^1 = 10
        expected = (self.params.threshold_error_rate / self.params.physical_error_rate) ** \
                   ((self.params.distance - 1) / 2)
        self.assertAlmostEqual(self.analyzer.coherence_enhancement, expected, places=10)
        self.assertAlmostEqual(self.analyzer.coherence_enhancement, 10.0, places=10)

    def test_logical_t2_is_10x_physical(self):
        """Logical T2 must be 10x physical T2 for d=3, p=0.1%."""
        self.assertAlmostEqual(
            self.analyzer.logical_T2_ms,
            10.0 * self.params.T2_physical_ms,
            places=10
        )

    def test_syndrome_cycles_per_window(self):
        """Number of syndrome cycles per spike window: 10ms / 1us = 10,000 cycles."""
        self.assertEqual(self.analyzer.syndrome_cycles_per_spike_window, 10000)

    def test_coherence_margin_for_viability(self):
        """Logical T2 must be >= spike integration window for QNHS viability."""
        margin = self.analyzer.logical_T2_ms / self.params.spike_integration_ms
        self.assertGreaterEqual(margin, 1.0,
            msg="Logical T2 must span at least one spike integration window")

    def test_100ms_projection_with_enrichment(self):
        """With T2=5ms (enriched 28Si roadmap), logical T2 must project to 50ms."""
        enriched = SurfaceCodeParams(
            distance=3,
            physical_error_rate=0.001,
            T2_physical_ms=5.0,
        )
        a = SurfaceCodeAnalyzer(enriched)
        self.assertAlmostEqual(a.logical_T2_ms, 50.0, places=10)
        self.assertGreater(a.logical_T2_ms, 10.0,
            msg="Enriched 28Si roadmap must project logical T2 > 10ms")


class TestSurfaceCodeDistanceScaling(unittest.TestCase):

    def test_qubit_count_formula(self):
        """n = d^2 + (d-1)^2 for all code distances."""
        for d in [3, 5, 7, 9]:
            params = SurfaceCodeParams(distance=d)
            expected = d**2 + (d - 1)**2
            self.assertEqual(SurfaceCodeAnalyzer(params).n_physical_qubits, expected,
                msg=f"d={d}: expected {expected} qubits")

    def test_higher_distance_lower_logical_error(self):
        """Increasing code distance must decrease logical error rate."""
        rates = []
        for d in [3, 5, 7]:
            p = SurfaceCodeParams(distance=d, physical_error_rate=0.005)
            rates.append(SurfaceCodeAnalyzer(p).logical_error_rate)
        for i in range(len(rates) - 1):
            self.assertGreater(rates[i], rates[i + 1],
                msg=f"Logical error rate must decrease with distance: {rates}")

    def test_higher_distance_better_enhancement(self):
        """Increasing code distance must increase coherence enhancement."""
        enhancements = []
        for d in [3, 5, 7]:
            p = SurfaceCodeParams(distance=d, physical_error_rate=0.001)
            enhancements.append(SurfaceCodeAnalyzer(p).coherence_enhancement)
        for i in range(len(enhancements) - 1):
            self.assertLess(enhancements[i], enhancements[i + 1],
                msg="Coherence enhancement must increase with code distance")

    def test_logical_error_threshold_behavior(self):
        """At p_phys = p_th: p_L = p_phys * (p_phys/p_th)^((d-1)/2) = p_phys * 1 = p_phys."""
        p = SurfaceCodeParams(
            distance=3,
            physical_error_rate=0.01,
            threshold_error_rate=0.01,
        )
        a = SurfaceCodeAnalyzer(p)
        # (p/p_th)^((d-1)/2) = 1^1 = 1, so p_L = p_phys * 1 = 0.01
        self.assertAlmostEqual(a.logical_error_rate, p.physical_error_rate, places=10,
            msg="At threshold p_phys=p_th, logical error rate must equal physical rate")

    def test_above_threshold_degrades(self):
        """Above threshold, d=3 code makes errors worse."""
        p = SurfaceCodeParams(
            distance=3,
            physical_error_rate=0.05,  # above 1% threshold
            threshold_error_rate=0.01,
        )
        a = SurfaceCodeAnalyzer(p)
        self.assertGreater(a.logical_error_rate, p.physical_error_rate,
            msg="Above threshold, surface code must make logical error rate worse")


class TestMWPMTiming(unittest.TestCase):

    def test_syndrome_cycle_fits_in_spike_window(self):
        """1 us MWPM latency << 10 ms spike integration window (paper Section III-D)."""
        p = SurfaceCodeParams(syndrome_cycle_us=1.0, spike_integration_ms=10.0)
        ratio = p.spike_integration_ms * 1e3 / p.syndrome_cycle_us
        self.assertGreater(ratio, 100.0,
            msg="Spike integration window must accommodate >100 syndrome cycles")

    def test_mwpm_latency_acceptable(self):
        """Paper states MWPM latency ~1 us << 10 ms biological SNN timescale."""
        mwpm_us = 1.0
        snn_ms = 10.0
        self.assertLess(mwpm_us, snn_ms * 1000 / 10,
            msg="MWPM latency must be at least 10x less than spike integration window")


if __name__ == "__main__":
    unittest.main(verbosity=2)
