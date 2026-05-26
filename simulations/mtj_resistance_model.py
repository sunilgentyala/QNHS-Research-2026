"""
PMA-MTJ Resistance State Modeling for QNHS Synaptic Plane
Quantum-Neuromorphic Hybrid Substrate (QNHS)
IEEE-NANO 2026 / ACM NANOCOM 2026

Models the four distinguishable resistance states {R0, R1, R2, R3}
in a PMA-MTJ crossbar with TMR > 200%.
SOT switching between states with Landauer-Buttiker formalism.

Author: Sunil Gentyala
ORCID: 0009-0005-2642-3479
GitHub: https://github.com/sunilgentyala/QNHS-Research-2026
"""

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from typing import List


@dataclass
class MTJDevice:
    """PMA-MTJ device parameters from paper Section V-B."""
    diameter_nm: float = 20.0
    tmr_ratio_pct: float = 200.0
    R_P_kohm: float = 5.0
    n_states: int = 4
    switching_energy_fJ: float = 0.1
    retention_barrier_kT: float = 60.0
    temp_K: float = 1.0

    @property
    def R_AP_kohm(self) -> float:
        return self.R_P_kohm * (1 + self.tmr_ratio_pct / 100.0)

    @property
    def resistance_states_kohm(self) -> List[float]:
        r0 = self.R_P_kohm
        r3 = self.R_AP_kohm
        step = (r3 - r0) / (self.n_states - 1)
        return [r0 + i * step for i in range(self.n_states)]

    def switching_probability(self, J_critical_ratio: float) -> float:
        """
        Macrospin switching probability.
        For J >= J_c: deterministic spin-torque switching -> p = 1.0.
        For J < J_c: Neel-Brown thermally activated switching.
        J_critical_ratio = J_applied / J_critical (0 to 1.5+)
        """
        if J_critical_ratio <= 0:
            return 0.0
        if J_critical_ratio >= 1.0:
            # Above critical current: spin-torque overcomes damping deterministically
            return 1.0
        kB = 1.38e-23
        T = max(self.temp_K, 1e-3)  # guard against exactly 0 K
        E_b = self.retention_barrier_kT * kB * 300.0  # barrier at 300K reference
        E_eff = E_b * (1 - J_critical_ratio) ** 1.5   # current-reduced barrier
        tau0 = 1e-9
        tau_ms = 1.0
        exponent = E_eff / (kB * T)
        if exponent > 700:
            return 0.0  # switching time >> pulse duration: no switching
        return 1 - np.exp(-tau_ms * 1e-3 / (tau0 * np.exp(exponent)))

    def read_current_nA(self, state_idx: int, V_read_mV: float = 50.0) -> float:
        R = self.resistance_states_kohm[state_idx]
        return V_read_mV / R * 1e3


def simulate_crossbar(n_rows: int = 16, n_cols: int = 16, seed: int = 99) -> np.ndarray:
    """
    Simulate a small MTJ crossbar with random 2-bit weight assignment.
    Returns resistance state matrix.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(0, 4, size=(n_rows, n_cols))


def plot_mtj_characteristics(device: MTJDevice):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    fig.suptitle(
        "PMA-MTJ Synaptic Device Characteristics\n"
        "QNHS SSP (Spintronic Synaptic Plane) | IEEE-NANO 2026",
        fontsize=10,
    )

    # Panel 1: Resistance states
    states = device.resistance_states_kohm
    state_labels = [f"R{i}\n({s:.1f} kΩ)" for i, s in enumerate(states)]
    colors = ["#1a5276", "#2980b9", "#85c1e9", "#d6eaf8"]
    bars = axes[0].bar(range(4), states, color=colors, edgecolor="black", linewidth=0.8)
    axes[0].set_xticks(range(4))
    axes[0].set_xticklabels(state_labels, fontsize=8)
    axes[0].set_ylabel("Resistance (kΩ)")
    axes[0].set_title(f"Four Resistance States\n(TMR = {device.tmr_ratio_pct:.0f}%)")
    for bar, val in zip(bars, states):
        axes[0].text(bar.get_x() + bar.get_width()/2, val + 0.1, f"{val:.1f}",
                     ha="center", va="bottom", fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)

    # Panel 2: Switching probability vs current ratio
    J_ratios = np.linspace(0, 1.5, 200)
    probs_1K = [device.switching_probability(j) for j in J_ratios]
    device_300 = MTJDevice(temp_K=300)
    probs_300K = [device_300.switching_probability(j) for j in J_ratios]
    axes[1].plot(J_ratios, probs_1K, "b-", lw=2, label="T = 1 K (QNHS)")
    axes[1].plot(J_ratios, probs_300K, "r--", lw=2, label="T = 300 K")
    axes[1].set_xlabel("J / J_critical")
    axes[1].set_ylabel("Switching Probability")
    axes[1].set_title("Thermally Activated Switching\nvs. Applied Current")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    axes[1].set_ylim(-0.05, 1.05)

    # Panel 3: Crossbar weight map (16x16)
    weights = simulate_crossbar(16, 16)
    im = axes[2].imshow(weights, cmap="Blues", vmin=0, vmax=3, aspect="auto")
    cbar = plt.colorbar(im, ax=axes[2], ticks=[0, 1, 2, 3])
    cbar.set_ticklabels(["R0 (P)", "R1", "R2", "R3 (AP)"])
    axes[2].set_title("16×16 MTJ Crossbar\nWeight State Map (2-bit/synapse)")
    axes[2].set_xlabel("Column (Postsynaptic)")
    axes[2].set_ylabel("Row (Presynaptic)")

    plt.tight_layout()
    plt.savefig("../figures/mtj_characteristics.png", dpi=150, bbox_inches="tight")
    print("Saved: figures/mtj_characteristics.png")
    plt.show()


if __name__ == "__main__":
    device = MTJDevice()
    print("=" * 50)
    print("  PMA-MTJ Device Parameters")
    print("=" * 50)
    print(f"  Diameter:          {device.diameter_nm} nm")
    print(f"  TMR ratio:         {device.tmr_ratio_pct:.0f}%")
    print(f"  R_P:               {device.R_P_kohm:.1f} kΩ")
    print(f"  R_AP:              {device.R_AP_kohm:.1f} kΩ")
    print(f"  Resistance states: {[f'{r:.2f} kΩ' for r in device.resistance_states_kohm]}")
    print(f"  Switching energy:  {device.switching_energy_fJ} fJ")
    print(f"  Retention (Δ):     {device.retention_barrier_kT} k_B T")
    print("=" * 50)
    plot_mtj_characteristics(device)
