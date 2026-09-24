"""
Re-preparation mode under realistic noise.

In re-preparation mode the synaptic amplitude vector is stored classically and a
k-qubit register is prepared, measured and discarded on every presynaptic spike.
This module builds the preparation circuit explicitly (Mottonen uniformly
controlled Ry rotations, i.e. Grover-Rudolph amplitude loading) and runs it as a
density-matrix simulation with:

  * depolarizing error after every 1-qubit and 2-qubit gate,
  * pure dephasing of every qubit for the duration of every gate (T2),
  * symmetric readout bit-flip error.

The output is the measured weight distribution, compared with the ideal one by
total variation distance (TVD) and by the error in the mean weight.

For real non-negative amplitudes and k qubits the circuit uses 2^k - 1 Ry
rotations and 2^k - 2 CNOTs (15 and 14 for k = 4).
"""

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

I2 = np.eye(2)
X = np.array([[0, 1], [1, 0]], dtype=float)
Z = np.array([[1, 0], [0, -1]], dtype=float)
Y = np.array([[0, -1j], [1j, 0]])


def ry(theta: float) -> np.ndarray:
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=float)


# ---------------------------------------------------------------- circuit
def _gray(i: int) -> int:
    return i ^ (i >> 1)


def uniformly_controlled_ry(target: int, controls: List[int], thetas: np.ndarray) -> List[Tuple]:
    """Decompose a uniformly controlled Ry into Ry + CNOT (Mottonen et al.).

    thetas[b] is the angle applied when the control register (controls[0] is
    the most significant bit) holds the integer b.
    """
    n = len(controls)
    if n == 0:
        return [("ry", target, float(thetas[0]))]
    size = 2 ** n
    # theta_i = sum_j M_ij alpha_j with M_ij = (-1)^(b_i . g_j)
    M = np.empty((size, size))
    for i in range(size):
        for j in range(size):
            M[i, j] = (-1) ** bin(i & _gray(j)).count("1")
    alphas = np.linalg.solve(M, thetas)
    ops = []
    for j in range(size):
        ops.append(("ry", target, float(alphas[j])))
        changed = _gray(j) ^ _gray((j + 1) % size)
        bit = changed.bit_length() - 1          # bit position, 0 = least significant
        ctrl = controls[n - 1 - bit]             # controls[0] is the most significant
        ops.append(("cx", ctrl, target))
    return ops


def state_prep_circuit(probs: np.ndarray) -> List[Tuple]:
    """Circuit preparing sum_l sqrt(p_l)|l> from |0...0> (qubit 0 = MSB)."""
    probs = np.asarray(probs, dtype=float)
    probs = probs / probs.sum()
    k = int(round(np.log2(len(probs))))
    ops: List[Tuple] = []
    for q in range(k):
        n_pref = 2 ** q
        block = 2 ** (k - q)
        thetas = np.zeros(n_pref)
        for b in range(n_pref):
            seg = probs[b * block:(b + 1) * block]
            tot = seg.sum()
            left = seg[: block // 2].sum()
            thetas[b] = 0.0 if tot <= 0 else 2 * np.arccos(np.sqrt(np.clip(left / tot, 0, 1)))
        ops += uniformly_controlled_ry(q, list(range(q)), thetas)
    return ops


def gate_counts(ops: List[Tuple]) -> Tuple[int, int]:
    return sum(o[0] == "ry" for o in ops), sum(o[0] == "cx" for o in ops)


# ---------------------------------------------------------------- simulator
def _embed(op: np.ndarray, qubit: int, k: int) -> np.ndarray:
    mats = [I2] * k
    mats[qubit] = op
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def _cnot(ctrl: int, tgt: int, k: int) -> np.ndarray:
    dim = 2 ** k
    U = np.zeros((dim, dim))
    for s in range(dim):
        bits = [(s >> (k - 1 - q)) & 1 for q in range(k)]
        if bits[ctrl]:
            bits[tgt] ^= 1
        t = sum(b << (k - 1 - q) for q, b in enumerate(bits))
        U[t, s] = 1
    return U


def _depolarize(rho: np.ndarray, qubits: List[int], p: float, k: int) -> np.ndarray:
    """Single-qubit depolarizing channel of strength p on each listed qubit.

    Uses (1-p)rho + p/3 (X rho X + Y rho Y + Z rho Z)
       = (1 - 4p/3) rho + (4p/3) (I/2 on qubit q) x Tr_q(rho).
    """
    if p <= 0:
        return rho
    shape = [2] * (2 * k)
    for q in qubits:
        r = rho.reshape(shape)
        red = np.trace(r, axis1=q, axis2=k + q)                  # Tr_q rho
        mixed = np.expand_dims(np.expand_dims(red, q), k + q)    # restore axes
        mixed = mixed * (np.eye(2).reshape([2 if i in (q, k + q) else 1 for i in range(2 * k)]) / 2)
        rho = ((1 - 4 * p / 3) * r + (4 * p / 3) * mixed).reshape(rho.shape)
    return rho


_HAM_CACHE = {}


def _hamming(k: int) -> np.ndarray:
    if k not in _HAM_CACHE:
        idx = np.arange(2 ** k)
        x = idx[:, None] ^ idx[None, :]
        _HAM_CACHE[k] = np.vectorize(lambda v: bin(v).count("1"))(x)
    return _HAM_CACHE[k]


def _dephase_all(rho: np.ndarray, t_ns: float, T2_ns: float, k: int) -> np.ndarray:
    """Pure dephasing on every qubit for t_ns: each coherence between basis
    states differing on h qubits decays by exp(-t/T2)^h."""
    if T2_ns == np.inf:
        return rho
    return rho * np.exp(-t_ns / T2_ns) ** _hamming(k)


@dataclass
class NoiseModel:
    p1: float = 0.0            # depolarizing error per 1-qubit gate
    p2: float = 0.0            # depolarizing error per qubit per 2-qubit gate
    T2_us: float = np.inf      # dephasing time
    t1q_ns: float = 33.0       # 1-qubit gate time (pi pulse at 30 MHz Rabi)
    t2q_ns: float = 100.0      # 2-qubit gate time (assumed)
    readout: float = 0.0       # symmetric bit-flip probability per qubit

    @classmethod
    def ideal(cls) -> "NoiseModel":
        return cls()

    @classmethod
    def hot_qubit(cls) -> "NoiseModel":
        """~1.5 K: 98.6% 1q fidelity and ~2 us coherence (Yang et al. 2020).
        2-qubit error and readout error are assumptions (no 1 K values reported)."""
        return cls(p1=0.014, p2=0.03, T2_us=2.0, readout=0.02)

    @classmethod
    def from_benchmarks(cls, f1: float, f2: float, readout: float, T2_us: float = np.inf) -> "NoiseModel":
        """Map benchmarked average gate fidelities onto this model's channels.

        A 1-qubit depolarizing channel with Pauli error p has average gate
        infidelity 2p/3, so p1 = 1.5 (1 - f1). Independent depolarizing of
        strength p on both qubits of a 2-qubit gate gives average infidelity
        8p/5 to first order, so p2 = (1 - f2) / 1.6. Benchmarked fidelities
        already contain dephasing during the gate, so T2 defaults to infinity
        (no separate dephasing channel) to avoid counting it twice.
        """
        return cls(p1=1.5 * (1.0 - f1), p2=(1.0 - f2) / 1.6, T2_us=T2_us, readout=readout)

    @classmethod
    def huang_1k(cls, with_T2star: bool = False) -> "NoiseModel":
        """~1 K, Huang et al., Nature 627 (2024) 772: 1q Clifford fidelity 99.85%,
        2q (DCZ, Bayesian tomography) 98.92%, readout 99.34% (even parity) and
        96.15% (odd parity), T2* ~2.3 us and Hahn T2 ~33 us at 1 K. Readout is
        modelled as a symmetric 2% flip, inside that parity range. These are the
        best values of one study, not a single calibrated operating point.
        with_T2star adds a T2* dephasing channel on top (double counts dephasing;
        a pessimistic bound)."""
        return cls.from_benchmarks(0.9985, 0.9892, readout=0.02,
                                   T2_us=2.3 if with_T2star else np.inf)

    @classmethod
    def millikelvin(cls) -> "NoiseModel":
        """Foundry devices at mK: >99% fidelities, T2(Hahn) up to 1.9 ms
        (Steinacker et al. 2025). Error values are representative choices."""
        return cls(p1=0.001, p2=0.01, T2_us=1900.0, readout=0.005)


def simulate_distribution(probs: np.ndarray, noise: NoiseModel) -> np.ndarray:
    """Measured basis-state distribution after noisy preparation + readout."""
    probs = np.asarray(probs, dtype=float)
    probs = probs / probs.sum()
    k = int(round(np.log2(len(probs))))
    dim = 2 ** k
    rho = np.zeros((dim, dim), dtype=complex)
    rho[0, 0] = 1.0
    T2_ns = noise.T2_us * 1e3
    for op in state_prep_circuit(probs):
        if op[0] == "ry":
            U = _embed(ry(op[2]), op[1], k)
            rho = U @ rho @ U.T
            rho = _dephase_all(rho, noise.t1q_ns, T2_ns, k)
            rho = _depolarize(rho, [op[1]], noise.p1, k)
        else:
            U = _cnot(op[1], op[2], k)
            rho = U @ rho @ U.T
            rho = _dephase_all(rho, noise.t2q_ns, T2_ns, k)
            rho = _depolarize(rho, [op[1], op[2]], noise.p2, k)
    dist = np.clip(np.real(np.diag(rho)), 0, None)
    dist /= dist.sum()
    if noise.readout > 0:
        flip = np.array([[1 - noise.readout, noise.readout], [noise.readout, 1 - noise.readout]])
        R = flip
        for _ in range(k - 1):
            R = np.kron(R, flip)
        dist = R @ dist
    return dist


def tvd(p: np.ndarray, q: np.ndarray) -> float:
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def mean_weight(dist: np.ndarray) -> float:
    basis = np.linspace(0.0, 1.0, len(dist))
    return float(np.dot(dist, basis))


def prep_duration_ns(k: int, noise: NoiseModel) -> float:
    n1, n2 = 2 ** k - 1, 2 ** k - 2
    return n1 * noise.t1q_ns + n2 * noise.t2q_ns


def random_targets(k: int, n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.dirichlet(np.ones(2 ** k), size=n)


def evaluate(noise: NoiseModel, k: int = 4, n: int = 50, seed: int = 0) -> dict:
    """Mean/percentile TVD and mean-weight error over random target distributions."""
    tv, dw = [], []
    for p in random_targets(k, n, seed):
        q = simulate_distribution(p, noise)
        tv.append(tvd(p, q))
        dw.append(abs(mean_weight(q) - mean_weight(p)))
    tv, dw = np.array(tv), np.array(dw)
    return {"tvd_mean": float(tv.mean()), "tvd_p95": float(np.percentile(tv, 95)),
            "dw_mean": float(dw.mean()), "dw_p95": float(np.percentile(dw, 95))}


if __name__ == "__main__":
    for name, nm in (("ideal", NoiseModel.ideal()), ("hot (~1.5 K)", NoiseModel.hot_qubit()),
                     ("millikelvin", NoiseModel.millikelvin())):
        r = evaluate(nm)
        print(f"{name:14s} TVD={r['tvd_mean']:.4f}  |d<w>|={r['dw_mean']:.4f}  "
              f"prep time={prep_duration_ns(4, nm):.0f} ns")
