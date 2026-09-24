"""
Unit tests for QNHS synaptic energy model.
Validates Eq. (3): E_syn = E_MTJ + E_qubit + E_CMOS ~ 11 fJ

Run: python -m pytest tests/test_energy_model.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from simulations.energy_model import (
    QNHSEnergyModel, MTJParams, QubitParams, CMOSParams
)


class TestMTJEnergyComponent(unittest.TestCase):

    def setUp(self):
        self.model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())

    def test_mtj_energy_is_01_fJ(self):
        """MTJ SOT switching energy must be ~0.1 fJ (paper Section IV-A)."""
        e = self.model.e_mtj_fJ()
        self.assertAlmostEqual(e, 0.1, places=3,
            msg="E_MTJ must equal 0.1 fJ per Landauer-Buttiker SOT model")

    def test_mtj_positive(self):
        self.assertGreater(self.model.e_mtj_fJ(), 0)

    def test_mtj_scales_with_pulse_width(self):
        """Doubling pulse duration doubles E_MTJ (linear in tau)."""
        p1 = MTJParams(pulse_duration_ns=1.0)
        p2 = MTJParams(pulse_duration_ns=2.0)
        m1 = QNHSEnergyModel(p1, QubitParams(), CMOSParams())
        m2 = QNHSEnergyModel(p2, QubitParams(), CMOSParams())
        self.assertAlmostEqual(m2.e_mtj_fJ() / m1.e_mtj_fJ(), 2.0, places=5)


class TestQubitEnergyComponent(unittest.TestCase):

    def setUp(self):
        self.model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())

    def test_qubit_energy_close_to_1_fJ(self):
        """Qubit gate energy must be ~1 fJ (30 nW * 33 ns, paper Section IV-A)."""
        e = self.model.e_qubit_fJ()
        self.assertGreater(e, 0.8, msg="E_qubit should be ~1 fJ")
        self.assertLess(e, 1.2, msg="E_qubit should be ~1 fJ")

    def test_qubit_energy_formula(self):
        """E_qubit = P_gate [nW] * t_pi [ns] converted to fJ."""
        q = QubitParams(gate_power_nW=10.0, pi_pulse_ns=100.0)
        m = QNHSEnergyModel(MTJParams(), q, CMOSParams())
        expected_fJ = 10e-9 * 100e-9 * 1e15  # 1 fJ
        self.assertAlmostEqual(m.e_qubit_fJ(), expected_fJ, places=5)


class TestCMOSEnergyComponent(unittest.TestCase):

    def setUp(self):
        self.model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())

    def test_cmos_energy_is_10_fJ(self):
        """Cryo-CMOS peripheral energy must be 10 fJ (paper Section IV-A)."""
        e = self.model.e_cmos_fJ()
        self.assertAlmostEqual(e, 10.0, places=1,
            msg="E_CMOS must be ~10 fJ per Patra et al. [14] 3nm FinFET at 1K")


class TestTotalSynapticEnergy(unittest.TestCase):

    def setUp(self):
        self.model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())

    def test_total_energy_approximately_11_fJ(self):
        """Total E_syn must be ~11 fJ (paper Section IV-A, Table I)."""
        e = self.model.total_energy_fJ()
        self.assertGreater(e, 10.5, msg="E_syn must be approximately 11 fJ")
        self.assertLess(e, 12.0, msg="E_syn must be approximately 11 fJ")

    def test_total_is_sum_of_components(self):
        m = self.model
        self.assertAlmostEqual(
            m.total_energy_fJ(),
            m.e_mtj_fJ() + m.e_qubit_fJ() + m.e_cmos_fJ(),
            places=10
        )

    def test_cmos_dominates(self):
        """E_CMOS must be the dominant contributor (paper Section IV-A)."""
        m = self.model
        self.assertGreater(m.e_cmos_fJ(), m.e_mtj_fJ())
        self.assertGreater(m.e_cmos_fJ(), m.e_qubit_fJ())

    def test_wall_plug_advantage_at_carnot_limit(self):
        """Even an ideal (Carnot) refrigerator leaves only a ~3x edge over H100."""
        r = self.model.refrigeration_overhead(fraction_of_carnot=1.0)
        self.assertGreater(r["wall_plug_advantage_x"], 2.5)
        self.assertLess(r["wall_plug_advantage_x"], 3.5)

    def test_realistic_cryocooler_erases_advantage(self):
        """At 10% of Carnot the wall-plug energy exceeds the H100 baseline."""
        r = self.model.refrigeration_overhead(fraction_of_carnot=0.1)
        self.assertLess(r["wall_plug_advantage_x"], 1.0)

    def test_device_level_advantage_three_orders(self):
        """Device-level E_syn advantage must be ~3 orders of magnitude over H100 (10 pJ vs 11 fJ)."""
        r = self.model.refrigeration_overhead()
        self.assertGreater(r["device_advantage_x"], 500,
            msg="Device advantage must exceed 500x (approaching 3 orders over H100)")
        self.assertLess(r["device_advantage_x"], 2000,
            msg="Device advantage bounded by E_syn > 5 fJ")

    def test_components_all_positive(self):
        m = self.model
        self.assertGreater(m.e_mtj_fJ(), 0)
        self.assertGreater(m.e_qubit_fJ(), 0)
        self.assertGreater(m.e_cmos_fJ(), 0)


class TestRefrigerationOverhead(unittest.TestCase):

    def test_carnot_bound_at_1K(self):
        """Carnot work to remove heat at 1 K and reject at 300 K is 299 J/J."""
        m = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())
        r = m.refrigeration_overhead(fraction_of_carnot=1.0)
        self.assertAlmostEqual(r["cooling_factor"], 300.0, places=6)
        self.assertAlmostEqual(r["e_wall_plug_fJ"], r["e_syn_fJ"] * 300.0, places=6)

    def test_breakeven_efficiency(self):
        """Break-even refrigerator efficiency must reproduce the H100 baseline."""
        m = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())
        f = m.breakeven_fraction_of_carnot()
        r = m.refrigeration_overhead(fraction_of_carnot=f)
        self.assertAlmostEqual(r["e_wall_plug_fJ"], 10000.0, places=3)

    def test_refrigeration_reduces_advantage(self):
        m = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())
        r = m.refrigeration_overhead()
        self.assertLess(
            r["wall_plug_advantage_x"],
            r["device_advantage_x"],
            msg="Refrigeration must reduce the net efficiency advantage"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
