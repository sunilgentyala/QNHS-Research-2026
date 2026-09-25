"""
Can the Q-STDP update (3) be applied to a coherently held register?

The update maps amplitudes alpha_l -> (1 + c d_l) alpha_l / sqrt(Z), with
d_l = w_l - <w> and Z = 1 + c^2 Var(w). Two facts limit a coherent version.

1. It is not a quantum channel. The map depends on the state through <w>, so
   it is nonlinear in the density matrix; no CPTP map (and hence no unitary,
   with or without ancillas and without post-selection) can reproduce it on
   every input. `nonlinearity_gap` shows this on a mixture of two states.

2. With <w> supplied classically, the fixed diagonal operator
   F = diag(1 + c d_l) / s, s = max_l |1 + c d_l|, satisfies F^dag F <= I and
   is the success branch of a two-outcome measurement. It can be realized with
   one ancilla and a uniformly controlled Ry on the ancilla (k controls):
   2^k rotations and 2^k CNOTs, then an ancilla measurement. Success yields
   exactly the update (3) with probability Z / s^2; failure leaves a state
   that no longer carries the distribution and must be re-prepared from a
   classical copy. Knowing <w> already requires that classical copy.
"""

import numpy as np


def qstdp_update(p: np.ndarray, basis: np.ndarray, c: float) -> np.ndarray:
    d = basis - float(np.dot(p, basis))
    q = p * (1.0 + c * d) ** 2
    return q / q.sum()


def success_probability(p: np.ndarray, basis: np.ndarray, c: float) -> float:
    d = basis - float(np.dot(p, basis))
    s = float(np.max(np.abs(1.0 + c * d)))
    return float(np.dot(p, (1.0 + c * d) ** 2)) / s ** 2


def filter_gate_counts(k: int) -> dict:
    """Ancilla-assisted filter: uniformly controlled Ry with k controls."""
    return {"ancillas": 1, "ry": 2 ** k, "cnot": 2 ** k, "ancilla_measurements": 1}


def nonlinearity_gap(k: int = 4, c: float = 0.5, seed: int = 0) -> float:
    """Max |T(mix) - mix(T)| over basis probabilities for a 50/50 mixture of two
    random distributions. A linear map would give zero. Because the update is
    diagonal in the weight basis, its action on diagonal density matrices is
    fully described by the probability vectors used here."""
    rng = np.random.default_rng(seed)
    basis = np.linspace(0.0, 1.0, 2 ** k)
    p1, p2 = rng.dirichlet(np.ones(2 ** k), size=2)
    lhs = qstdp_update(0.5 * (p1 + p2), basis, c)
    rhs = 0.5 * (qstdp_update(p1, basis, c) + qstdp_update(p2, basis, c))
    return float(np.max(np.abs(lhs - rhs)))


def filter_cost(k: int = 4, c_values=(0.001, 0.01, 0.05), n: int = 200, seed: int = 0,
                t1q_ns: float = 33.0, t2q_ns: float = 100.0) -> dict:
    rng = np.random.default_rng(seed)
    basis = np.linspace(0.0, 1.0, 2 ** k)
    ps = rng.dirichlet(np.ones(2 ** k), size=n)
    g = filter_gate_counts(k)
    out = {"gates": g, "gate_time_ns": g["ry"] * t1q_ns + g["cnot"] * t2q_ns, "by_c": {}}
    for c in c_values:
        succ = np.array([success_probability(p, basis, c) for p in ps])
        out["by_c"][str(c)] = {"p_success_mean": float(succ.mean()), "p_success_min": float(succ.min()),
                               "expected_attempts": float(np.mean(1.0 / succ))}
    out["nonlinearity_gap_c0.5"] = nonlinearity_gap(k, 0.5, seed)
    return out


if __name__ == "__main__":
    print(filter_cost())
