"""
Monte Carlo uncertainty analysis of QNHS energy per synaptic event.

Every input of the energy model is uncertain, so point estimates hide how much
the conclusion depends on the assumptions. Each parameter is drawn from a
log-uniform range. The ranges are modelling assumptions, stated here so they
can be changed:

  E_MTJ        0.1 - 10 fJ      SOT write energy per event
  P_gate       10 - 100 nW      qubit drive power during a gate
  t_gate       33 ns            per gate
  n_gates      1 (hold mode) or 2^(k+1) - 3 = 29 (re-preparation, k = 4)
  E_CMOS       5 - 50 fJ        neuron, decoder and I/O logic at ~1 K
  eps          0.5% - 30%       refrigerator efficiency as a fraction of Carnot
  E_ref        3 - 30 pJ        GPU reference energy per synaptic operation

Outputs: the distribution of wall-plug energy, the probability that QNHS beats
the reference, and Spearman rank correlations as a global sensitivity measure.
"""

import numpy as np

T_HOT, T_COLD = 300.0, 1.0
CARNOT = (T_HOT - T_COLD) / T_COLD


def _logu(rng, lo, hi, n):
    return np.exp(rng.uniform(np.log(lo), np.log(hi), n))


def _rank(x):
    r = np.empty(len(x))
    r[np.argsort(x)] = np.arange(len(x))
    return r


def spearman(x, y) -> float:
    return float(np.corrcoef(_rank(x), _rank(y))[0, 1])


def sample(n: int = 100_000, mode: str = "reprep", k: int = 4, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    e_mtj = _logu(rng, 0.1, 10.0, n)
    p_gate = _logu(rng, 10.0, 100.0, n)
    n_gates = 1 if mode == "hold" else 2 ** (k + 1) - 3
    e_qubit = p_gate * 1e-9 * 33e-9 * n_gates * 1e15      # fJ
    e_cmos = _logu(rng, 5.0, 50.0, n)
    eps = _logu(rng, 0.005, 0.30, n)
    e_ref = _logu(rng, 3000.0, 30000.0, n)               # fJ
    e_syn = e_mtj + e_qubit + e_cmos
    e_wall = e_syn * (1.0 + CARNOT / eps)
    ratio = e_ref / e_wall
    inputs = {"E_MTJ": e_mtj, "P_gate": p_gate, "E_CMOS": e_cmos, "eps": eps, "E_ref": e_ref}
    return {
        "mode": mode,
        "n": n,
        "e_syn_fJ_median": float(np.median(e_syn)),
        "e_syn_fJ_p5_p95": [float(np.percentile(e_syn, 5)), float(np.percentile(e_syn, 95))],
        "e_wall_pJ_median": float(np.median(e_wall) / 1000),
        "e_wall_pJ_p5_p95": [float(np.percentile(e_wall, 5) / 1000), float(np.percentile(e_wall, 95) / 1000)],
        "p_beats_reference": float(np.mean(ratio > 1.0)),
        "ratio_median": float(np.median(ratio)),
        "spearman_vs_ratio": {k_: spearman(v, ratio) for k_, v in inputs.items()},
        "_ratio": ratio,
        "_eps": eps,
        "_e_wall": e_wall,
    }


if __name__ == "__main__":
    for m in ("hold", "reprep"):
        r = sample(mode=m)
        print(m, {k: v for k, v in r.items() if not k.startswith("_")})
