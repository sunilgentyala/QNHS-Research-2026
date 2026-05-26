"""
Distance-3 Surface Code Analysis for QNHS Topological Error Protection
Quantum-Neuromorphic Hybrid Substrate (QNHS)
IEEE-NANO 2026 / ACM NANOCOM 2026

Analyzes the distance-3 surface code error suppression performance
for 28Si spin qubits in the QNHS architecture (Section III-D, IV-C).

Author: Sunil Gentyala
ORCID: 0009-0005-2642-3479
GitHub: https://github.com/sunilgentyala/QNHS-Research-2026
"""

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass


@dataclass
class SurfaceCodeParams:
    distance: int = 3
    physical_error_rate: float = 0.001  # <0.1% for 28Si spin qubits
    threshold_error_rate: float = 0.01  # ~1% surface code threshold
    syndrome_cycle_us: float = 1.0      # MWPM decoder latency [us]
    spike_integration_ms: float = 10.0  # SNN spike integration window [ms]
    T2_physical_ms: float = 1.0         # physical qubit T2 at 1K [ms]


class SurfaceCodeAnalyzer:
    """
    Analyzes distance-d surface code performance for QNHS logical coherence.
    Uses approximate suppression formula: p_L ~ (p_phys/p_th)^((d+1)/2)
    """

    def __init__(self, params: SurfaceCodeParams):
        self.p = params

    @property
    def n_physical_qubits(self) -> int:
        d = self.p.distance
        return d**2 + (d - 1)**2

    @property
    def logical_error_rate(self) -> float:
        """
        Logical error rate: p_L = p_phys * (p_phys/p_th)^((d-1)/2)
        Consistent with coherence_enhancement = (p_th/p_phys)^((d-1)/2).
        At p_phys = p_th: p_L = p_phys (no gain / no loss, at threshold).
        For p_phys << p_th: p_L << p_phys (exponential suppression).
        """
        p = self.p.physical_error_rate
        p_th = self.p.threshold_error_rate
        d = self.p.distance
        return p * (p / p_th) ** ((d - 1) / 2)

    @property
    def coherence_enhancement(self) -> float:
        p_th = self.p.threshold_error_rate
        p = self.p.physical_error_rate
        d = self.p.distance
        return (p_th / p) ** ((d - 1) / 2)

    @property
    def logical_T2_ms(self) -> float:
        return self.p.T2_physical_ms * self.coherence_enhancement

    @property
    def syndrome_cycles_per_spike_window(self) -> int:
        return int(self.p.spike_integration_ms * 1e3 / self.p.syndrome_cycle_us)

    def print_report(self):
        print("=" * 60)
        print("  Distance-3 Surface Code Performance (QNHS)")
        print("=" * 60)
        print(f"  Code distance (d):             {self.p.distance}")
        print(f"  Physical qubits per logical:   {self.n_physical_qubits}")
        print(f"  Physical error rate:           {self.p.physical_error_rate*100:.2f}%")
        print(f"  Surface code threshold:        {self.p.threshold_error_rate*100:.1f}%")
        print(f"  Logical error rate:            {self.logical_error_rate:.2e}")
        print(f"  Coherence enhancement factor:  {self.coherence_enhancement:.1f}x")
        print(f"  Physical T2 at 1K:             {self.p.T2_physical_ms:.1f} ms")
        print(f"  Logical T2 (projected):        {self.logical_T2_ms:.0f} ms")
        print(f"  Spike integration window:      {self.p.spike_integration_ms:.1f} ms")
        print(f"  Syndrome cycles per window:    {self.syndrome_cycles_per_spike_window}")
        margin = self.logical_T2_ms / self.p.spike_integration_ms
        print(f"  Coherence margin:              {margin:.1f}x (>1 = viable)")
        print("=" * 60)
        if margin >= 5:
            print("  STATUS: Comfortably within QNHS operational requirements.")
        elif margin >= 1:
            print("  STATUS: Marginally viable; isotopic enrichment roadmap needed.")
        else:
            print("  STATUS: Insufficient; requires higher d or better physical T2.")


def plot_surface_code_scaling():
    """Show logical error rate and coherence vs code distance."""
    distances = [3, 5, 7, 9, 11]
    p_phys_values = [0.001, 0.005, 0.01]
    p_th = 0.01

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(
        "Surface Code Error Suppression for 28Si Spin Qubits\n"
        "QNHS Topological Protection | IEEE-NANO 2026",
        fontsize=10,
    )

    colors = ["#27ae60", "#e67e22", "#e74c3c"]
    labels = ["p_phys = 0.1% (28Si)", "p_phys = 0.5%", "p_phys = 1.0%"]

    for p_phys, color, label in zip(p_phys_values, colors, labels):
        p_L = [(p_phys / p_th) ** ((d + 1) / 2) for d in distances]
        coherence = [(p_th / p_phys) ** ((d - 1) / 2) for d in distances]
        axes[0].semilogy(distances, p_L, "o-", color=color, lw=2, label=label, markersize=6)
        axes[1].plot(distances, coherence, "s-", color=color, lw=2, label=label, markersize=6)

    axes[0].axhline(1e-6, color="gray", linestyle="--", alpha=0.6, label="Target p_L < 1e-6")
    axes[0].set_xlabel("Code Distance d")
    axes[0].set_ylabel("Logical Error Rate p_L")
    axes[0].set_title("Logical Error Rate vs. Code Distance")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    axes[1].axhline(10, color="green", linestyle="--", alpha=0.6, label="d=3 target (10x)")
    axes[1].set_xlabel("Code Distance d")
    axes[1].set_ylabel("T2 Enhancement Factor")
    axes[1].set_title("Coherence Enhancement vs. Code Distance")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("../figures/surface_code_scaling.png", dpi=150, bbox_inches="tight")
    print("Saved: figures/surface_code_scaling.png")
    plt.show()


if __name__ == "__main__":
    params = SurfaceCodeParams(
        distance=3,
        physical_error_rate=0.001,
        T2_physical_ms=1.0,
        spike_integration_ms=10.0,
    )
    analyzer = SurfaceCodeAnalyzer(params)
    analyzer.print_report()

    print("\nProjection with isotopic enrichment roadmap (T2 = 5 ms):")
    params_enhanced = SurfaceCodeParams(
        distance=3,
        physical_error_rate=0.001,
        T2_physical_ms=5.0,
    )
    SurfaceCodeAnalyzer(params_enhanced).print_report()
    plot_surface_code_scaling()
