"""
Q-STDP: Quantum Spike-Timing-Dependent Plasticity Simulation
Quantum-Neuromorphic Hybrid Substrate (QNHS)
IEEE-NANO 2026 / ACM NANOCOM 2026

Implements Eq. (3) from the paper:
  alpha_l^(t+1) = N[ alpha_l^(t) + eta * K(dt) * alpha_l^(t) ]
  K(dt) = A+ * exp(-dt/tau+) * Theta(dt) - A- * exp(+dt/tau-) * Theta(-dt)

Author: Sunil Gentyala
ORCID: 0009-0005-2642-3479
GitHub: https://github.com/sunilgentyala/QNHS-Research-2026
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple


class QSTDPSynapse:
    """
    Single quantum synapse with k-qubit amplitude encoding and Q-STDP learning.
    Weight distribution is maintained as complex probability amplitudes {alpha_l}.
    """

    def __init__(
        self,
        k: int = 4,
        eta: float = 0.05,
        A_plus: float = 0.2,
        A_minus: float = 0.21,
        tau_plus_ms: float = 20.0,
        tau_minus_ms: float = 20.0,
        seed: int = 42,
    ):
        self.k = k
        self.n_states = 2**k
        self.eta = eta
        self.A_plus = A_plus
        self.A_minus = A_minus
        self.tau_plus = tau_plus_ms
        self.tau_minus = tau_minus_ms
        rng = np.random.default_rng(seed)
        raw = rng.random(self.n_states) + 1j * rng.random(self.n_states) * 0.0
        self.alpha = raw / np.linalg.norm(raw)
        self.weight_basis = np.linspace(0.0, 1.0, self.n_states)

    def stdp_kernel(self, dt_ms: float) -> float:
        """STDP timing kernel K(dt). Positive dt = LTP, negative dt = LTD."""
        if dt_ms > 0:
            return self.A_plus * np.exp(-dt_ms / self.tau_plus)
        elif dt_ms < 0:
            return -self.A_minus * np.exp(dt_ms / self.tau_minus)
        return 0.0

    def update(self, dt_ms: float) -> None:
        """Apply Q-STDP amplitude update for a spike pair separated by dt_ms."""
        k_val = self.stdp_kernel(dt_ms)
        self.alpha = self.alpha + self.eta * k_val * self.alpha
        norm = np.linalg.norm(self.alpha)
        if norm > 1e-10:
            self.alpha /= norm

    def sample_weight(self) -> float:
        """Projective measurement: collapse |w_ij> to a weight basis state."""
        probs = np.abs(self.alpha) ** 2
        probs /= probs.sum()
        return float(np.random.choice(self.weight_basis, p=probs))

    def mean_weight(self) -> float:
        probs = np.abs(self.alpha) ** 2
        return float(np.dot(probs, self.weight_basis))

    def weight_entropy(self) -> float:
        """Shannon entropy of the weight probability distribution (bits)."""
        probs = np.abs(self.alpha) ** 2
        probs = probs[probs > 1e-12]
        return float(-np.sum(probs * np.log2(probs)))


def simulate_qstdp_learning(
    n_events: int = 500,
    dt_range_ms: Tuple[float, float] = (-50.0, 50.0),
    k: int = 4,
) -> dict:
    """
    Simulate Q-STDP learning on a single quantum synapse over a sequence
    of random spike pairs, and track weight distribution evolution.
    """
    synapse = QSTDPSynapse(k=k)
    rng = np.random.default_rng(0)
    dts = rng.uniform(*dt_range_ms, size=n_events)

    mean_weights, entropies, sampled = [], [], []
    for dt in dts:
        synapse.update(dt)
        mean_weights.append(synapse.mean_weight())
        entropies.append(synapse.weight_entropy())
        sampled.append(synapse.sample_weight())

    return {
        "dts": dts,
        "mean_weights": np.array(mean_weights),
        "entropies": np.array(entropies),
        "sampled_weights": np.array(sampled),
        "final_probs": np.abs(synapse.alpha) ** 2,
        "weight_basis": synapse.weight_basis,
    }


def plot_qstdp_results(results: dict):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    fig.suptitle(
        "Q-STDP Quantum Synaptic Learning Dynamics\n"
        "IEEE-NANO 2026 | Sunil Gentyala | QNHS Architecture",
        fontsize=11,
    )

    n = len(results["mean_weights"])

    # Panel 1: Mean weight evolution
    axes[0, 0].plot(results["mean_weights"], color="#2980b9", lw=1.2)
    axes[0, 0].set_xlabel("Spike Event Index")
    axes[0, 0].set_ylabel("Mean Weight <w>")
    axes[0, 0].set_title("Mean Weight Evolution Under Q-STDP")
    axes[0, 0].grid(alpha=0.3)

    # Panel 2: Weight entropy (Bayesian uncertainty)
    axes[0, 1].plot(results["entropies"], color="#8e44ad", lw=1.2)
    axes[0, 1].set_xlabel("Spike Event Index")
    axes[0, 1].set_ylabel("H(w) [bits]")
    axes[0, 1].set_title("Synaptic Weight Entropy (Uncertainty)")
    axes[0, 1].grid(alpha=0.3)

    # Panel 3: STDP kernel K(dt)
    dt_arr = np.linspace(-50, 50, 500)
    syn = QSTDPSynapse()
    kernel = np.array([syn.stdp_kernel(dt) for dt in dt_arr])
    axes[1, 0].plot(dt_arr, kernel, color="#e74c3c", lw=2)
    axes[1, 0].axhline(0, color="k", lw=0.8, linestyle="--")
    axes[1, 0].axvline(0, color="k", lw=0.8, linestyle="--")
    axes[1, 0].fill_between(dt_arr, kernel, 0, where=(kernel > 0), alpha=0.3, color="#2ecc71", label="LTP")
    axes[1, 0].fill_between(dt_arr, kernel, 0, where=(kernel < 0), alpha=0.3, color="#e74c3c", label="LTD")
    axes[1, 0].set_xlabel("Spike Timing Differential dt (ms)")
    axes[1, 0].set_ylabel("K(dt)")
    axes[1, 0].set_title("Q-STDP Temporal Kernel K(dt)")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=0.3)

    # Panel 4: Final weight probability distribution
    axes[1, 1].bar(
        results["weight_basis"],
        results["final_probs"],
        width=0.05,
        color="#f39c12",
        edgecolor="black",
        linewidth=0.5,
    )
    axes[1, 1].set_xlabel("Weight Basis State |w_l>")
    axes[1, 1].set_ylabel("|alpha_l|^2")
    axes[1, 1].set_title(f"Final Weight Distribution (k={int(np.log2(len(results['final_probs'])))} qubits)")
    axes[1, 1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig("../figures/qstdp_dynamics.png", dpi=150, bbox_inches="tight")
    print("Saved: figures/qstdp_dynamics.png")
    plt.show()


if __name__ == "__main__":
    print("Running Q-STDP simulation (k=4 qubits per synapse, 500 spike events)...")
    results = simulate_qstdp_learning(n_events=500, k=4)
    final_entropy = results["entropies"][-1]
    final_mean = results["mean_weights"][-1]
    print(f"Final mean weight:  {final_mean:.4f}")
    print(f"Final entropy:      {final_entropy:.4f} bits  (max = {int(np.log2(16))} bits)")
    plot_qstdp_results(results)
