"""
QNHS Energy Model: Synaptic Event Energy Decomposition
Quantum-Neuromorphic Hybrid Substrate (QNHS)
Research code accompanying the QNHS paper

Author: Sunil Gentyala
Affiliation: Independent Researcher, HCLTech (HCL America Inc.), Dallas, TX
ORCID: 0009-0005-2642-3479

Reference: Eq. (4) in the paper: E_syn = E_MTJ + E_qubit + E_CMOS
"""

import os
import numpy as np
import matplotlib.pyplot as plt

FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")
from dataclasses import dataclass


@dataclass
class MTJParams:
    diameter_nm: float = 20.0        # pillar diameter [nm]
    damping_constant: float = 0.015  # Gilbert damping alpha_G
    anisotropy_field_T: float = 0.5  # mu0 * H_k [Tesla]
    pulse_duration_ns: float = 1.0   # current pulse duration [ns]
    MgO_thickness_nm: float = 0.9    # tunnel barrier thickness


@dataclass
class QubitParams:
    gate_power_nW: float = 30.0      # gate drive power [nW] (30 nW * 33 ns = ~1 fJ)
    rabi_freq_MHz: float = 30.0      # Rabi frequency [MHz]
    pi_pulse_ns: float = 33.0        # pi-pulse duration [ns]
    T2_ms: float = 1.0               # assumed; ~2 us demonstrated above 1 K (Yang 2020)
    gate_fidelity: float = 0.999     # single-qubit gate fidelity (28Si)


@dataclass
class CMOSParams:
    process_node_nm: float = 3.0     # FinFET process node [nm]
    operating_temp_K: float = 1.0    # operating temperature [K]
    mobility_enhancement: float = 2.0  # carrier mobility at 1K vs 300K
    vdd_mV: float = 600.0            # supply voltage [mV]


class QNHSEnergyModel:
    """
    Decomposes synaptic event energy into three contributions:
    MTJ switching, qubit gate, and cryo-CMOS peripheral overhead.
    """

    def __init__(self, mtj: MTJParams, qubit: QubitParams, cmos: CMOSParams):
        self.mtj = mtj
        self.qubit = qubit
        self.cmos = cmos
        self.kB = 1.380649e-23  # Boltzmann constant [J/K]
        self.hbar = 1.054571817e-34  # reduced Planck constant [J*s]
        self.mu_B = 9.2740100783e-24  # Bohr magneton [J/T]

    def e_mtj_fJ(self) -> float:
        """
        Electrical pulse energy delivered to the MTJ during SOT switching.
        E_MTJ = V_write * I_write * tau_pulse
        For a d=20nm PMA-MTJ: V=0.5V, I~200uA, tau=1ns -> ~0.1 fJ.
        Assumes a low-resistance SOT write path (~10 Ohm at 100 uA).
        """
        V_write = 1.0e-3    # SOT layer voltage [V] (low-R path, ~80 Ohm * 10 uA)
        I_write = 100.0e-6  # SOT critical current for 20nm device at J_c~10^8 A/cm^2
        tau_s = self.mtj.pulse_duration_ns * 1e-9
        return V_write * I_write * tau_s * 1e15  # convert to fJ

    def e_qubit_fJ(self) -> float:
        """
        Qubit gate energy: P_gate * t_pi
        P_gate = 1 nW (gate drive at 30 MHz Rabi frequency)
        t_pi = 1/(2*f_Rabi) = 33 ns
        """
        p_gate_W = self.qubit.gate_power_nW * 1e-9
        t_pi_s = self.qubit.pi_pulse_ns * 1e-9
        return p_gate_W * t_pi_s * 1e15  # fJ

    def e_cmos_fJ(self) -> float:
        """
        Cryo-CMOS peripheral energy dominates at ~10 fJ.
        Accounts for: LIF neuron, spike encoder, MWPM syndrome,
        I/O SerDes -- all in 3nm FinFET at 1K.
        Mobility enhancement of 2x partially offsets cooling overhead.
        """
        return 10.0  # assumed cryo-CMOS budget at 1K: LIF + MWPM + SerDes [fJ]

    def total_energy_fJ(self) -> float:
        return self.e_mtj_fJ() + self.e_qubit_fJ() + self.e_cmos_fJ()

    def refrigeration_overhead(self, fraction_of_carnot: float = 1.0,
                               T_hot_K: float = 300.0) -> dict:
        """
        Wall-plug energy including the work needed to pump the dissipated
        heat from T_cold to T_hot.

        The Carnot bound sets the minimum work per joule removed:
            W/Q >= (T_hot - T_cold) / T_cold  = 299 at 1 K from 300 K.
        Wall-plug energy is therefore E_syn * (1 + 299 / fraction_of_carnot).
        fraction_of_carnot = 1.0 is the ideal (best-case) refrigerator; real
        cryocoolers reach only a small fraction of it, which raises the cost.
        """
        T_cold = self.cmos.operating_temp_K
        carnot_work_per_joule = (T_hot_K - T_cold) / T_cold
        cooling_factor = 1.0 + carnot_work_per_joule / fraction_of_carnot
        e_syn = self.total_energy_fJ()
        e_wall_plug = e_syn * cooling_factor
        gpu_h100_fJ = 10000.0  # H100 ~10 pJ = 10,000 fJ per synaptic operation
        return {
            "e_syn_fJ": e_syn,
            "cooling_factor": cooling_factor,
            "e_wall_plug_fJ": e_wall_plug,
            "gpu_h100_fJ": gpu_h100_fJ,
            "device_advantage_x": gpu_h100_fJ / e_syn,
            "wall_plug_advantage_x": gpu_h100_fJ / e_wall_plug,
        }

    def breakeven_fraction_of_carnot(self, T_hot_K: float = 300.0) -> float:
        """Smallest refrigerator efficiency (fraction of Carnot) at which the
        wall-plug energy still matches the H100 baseline."""
        T_cold = self.cmos.operating_temp_K
        carnot_work_per_joule = (T_hot_K - T_cold) / T_cold
        max_cooling_factor = 10000.0 / self.total_energy_fJ()
        return carnot_work_per_joule / (max_cooling_factor - 1.0)

    def print_report(self):
        print("=" * 55)
        print("  QNHS Synaptic Event Energy Budget")
        print("=" * 55)
        print(f"  E_MTJ  (SOT write pulse):   {self.e_mtj_fJ():.3f} fJ")
        print(f"  E_qubit (gate drive):        {self.e_qubit_fJ():.3f} fJ")
        print(f"  E_CMOS  (cryo-CMOS periph): {self.e_cmos_fJ():.3f} fJ")
        print(f"  E_syn   (total):             {self.total_energy_fJ():.3f} fJ")
        print("-" * 55)
        r = self.refrigeration_overhead()
        print(f"  Wall-plug (Carnot limit):    {r['e_wall_plug_fJ']:.0f} fJ  ({r['cooling_factor']:.0f}x)")
        print(f"  Device-level advantage:      {r['device_advantage_x']:.0f}x vs H100")
        print(f"  Wall-plug advantage (ideal): {r['wall_plug_advantage_x']:.1f}x vs H100")
        print(f"  Break-even cryocooler:       {self.breakeven_fraction_of_carnot()*100:.0f}% of Carnot")
        print("=" * 55)


def plot_energy_comparison():
    model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())
    e_dev = model.total_energy_fJ()
    e_carnot = model.refrigeration_overhead()["e_wall_plug_fJ"]
    e_10pct = model.refrigeration_overhead(fraction_of_carnot=0.1)["e_wall_plug_fJ"]
    systems = ["NVIDIA H100\n(GPU)", "Intel\nLoihi 2", "IBM\nNorthPole", "QNHS\n(device)",
               "QNHS wall-plug\n(Carnot limit)", "QNHS wall-plug\n(10% of Carnot)"]
    energies_fJ = [10000.0, 1000.0, 500.0, e_dev, e_carnot, e_10pct]
    colors = ["#e74c3c", "#e67e22", "#f1c40f", "#27ae60", "#2ecc71", "#95a5a6"]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(systems, energies_fJ, color=colors, width=0.55, edgecolor="black", linewidth=0.8)
    ax.set_yscale("log")
    ax.set_ylabel("Energy per Synaptic Event (fJ)", fontsize=12)
    ax.set_title("QNHS vs. State-of-the-Art: Synaptic Energy Comparison\n"
                 "QNHS | Sunil Gentyala", fontsize=11)
    ax.set_ylim(1, 1e6)
    ax.axhline(y=10000, color="#e74c3c", linestyle="--", alpha=0.6, label="H100 baseline (10 pJ)")
    for bar, val in zip(bars, energies_fJ):
        ax.text(bar.get_x() + bar.get_width() / 2, val * 1.4,
                f"{val:,.0f} fJ", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    plt.savefig(os.path.join(FIG_DIR, "energy_comparison.png"), dpi=150, bbox_inches="tight")
    print("Saved: figures/energy_comparison.png")
    if "agg" not in plt.get_backend().lower():
        plt.show()


if __name__ == "__main__":
    model = QNHSEnergyModel(MTJParams(), QubitParams(), CMOSParams())
    model.print_report()
    plot_energy_comparison()
