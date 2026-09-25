"""
Monte Carlo uncertainty analysis of QNHS energy per synaptic event.

Every input of the energy model is uncertain, so point estimates hide how much
the conclusion depends on the assumptions. Each parameter is drawn from a
log-uniform range. The ranges are modelling assumptions, stated here so they
can be changed:

  E_MTJ        0.1 - 10 fJ      SOT write energy per event
  P_gate       10 - 100 nW      qubit drive power during a gate
  t_1q, t_2q   33 ns, 100 ns    single-qubit rotation and CNOT durations
  gates        hold mode: one 33 ns pulse per event
               re-preparation: 2^k - 1 rotations (33 ns) and 2^k - 2 CNOTs
               (100 ns), 15 and 14 for k = 4, i.e. 1.895 us of drive per event.
               Both gate types are assumed to draw the same drive power.
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


T_1Q_S, T_2Q_S = 33e-9, 100e-9


def drive_time_s(mode: str, k: int = 4) -> float:
    """Total gate-drive time per synaptic event.

    Earlier versions charged 33 ns to every gate of the re-preparation circuit,
    which undercounted the 100 ns CNOTs (0.96 us instead of 1.895 us for k = 4).
    """
    if mode == "hold":
        return T_1Q_S
    return (2 ** k - 1) * T_1Q_S + (2 ** k - 2) * T_2Q_S


def point_energy_fJ(mode: str, k: int = 4, p_gate_nW: float = 30.0,
                    e_mtj_fJ: float = 0.1, e_cmos_fJ: float = 10.0) -> float:
    """Device-level energy per event at the point values of the paper."""
    return e_mtj_fJ + p_gate_nW * 1e-9 * drive_time_s(mode, k) * 1e15 + e_cmos_fJ


def sample(n: int = 100_000, mode: str = "reprep", k: int = 4, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    e_mtj = _logu(rng, 0.1, 10.0, n)
    p_gate = _logu(rng, 10.0, 100.0, n)
    e_qubit = p_gate * 1e-9 * drive_time_s(mode, k) * 1e15   # fJ
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


# ---------------------------------------------------------------------------
# Workload-level model: sampling energy versus learning-update energy
# ---------------------------------------------------------------------------
# The per-event model above folds MTJ, gate drive and CMOS into one number. At
# the workload level two costs have different rates:
#   E_sample  per presynaptic spike: state loading (gate drive), readout
#             conversion and synaptic transmission (CMOS sample path).
#   E_learn   per Q-STDP update: 2^k multiply-adds on the stored probabilities,
#             2^k - 1 rotation-angle recomputations, and rewriting the angle
#             cells in the MTJ store.
# Workload energy per presynaptic spike = E_sample + u * E_learn, where u is the
# number of updates per presynaptic spike measured in the network experiment.
#
# E_learn digital logic: lower bound from 2^k int8 multiply-adds at 7 nm
# (0.07 pJ multiply + 0.007 pJ add, Jouppi et al. 2021, Table 2) = 1.23 pJ for
# k = 4; upper reference from the measured Loihi pairwise-STDP synaptic update,
# 120 pJ (Davies et al. 2018). The point value is the geometric mean, 12 pJ.
# Angle cells: 60 two-bit cells rewritten per update at E_MTJ each.
# Reference workload: Loihi measured 23.6 pJ per synaptic spike operation and
# 120 pJ per synaptic update (Davies et al. 2018).

E_LEARN_LO_FJ, E_LEARN_HI_FJ = 1230.0, 120000.0
E_LEARN_POINT_FJ = float(np.sqrt(E_LEARN_LO_FJ * E_LEARN_HI_FJ))
LOIHI_SOP_FJ, LOIHI_UPDATE_FJ = 23600.0, 120000.0
ANGLE_CELLS = 60


def sample_energy_fJ(mode: str = "reprep", k: int = 4, p_gate_nW: float = 30.0,
                     e_cmos_fJ: float = 10.0):
    return p_gate_nW * 1e-9 * drive_time_s(mode, k) * 1e15 + e_cmos_fJ


def learn_energy_fJ(e_update_fJ: float = E_LEARN_POINT_FJ, e_mtj_fJ: float = 0.1,
                    cells: int = ANGLE_CELLS):
    return e_update_fJ + cells * e_mtj_fJ


def workload_point(u: float, mode: str = "reprep", eps: float = 1.0) -> dict:
    """Wall-plug workload energy per presynaptic spike at the point values, for
    the update logic placed at 1 K (charged the Carnot factor) or at 300 K."""
    es, el = sample_energy_fJ(mode), learn_energy_fJ()
    f = 1.0 + CARNOT / eps
    return {"u": u, "eps": eps, "E_sample_fJ": es, "E_learn_fJ": el,
            "wall_learn_at_1K_pJ": (es + u * el) * f / 1000,
            "wall_learn_at_300K_pJ": (es * f + u * el) / 1000,
            "loihi_reference_pJ": (LOIHI_SOP_FJ + u * LOIHI_UPDATE_FJ) / 1000}


def workload_sample(u: float, n: int = 100_000, mode: str = "reprep", k: int = 4,
                    seed: int = 1) -> dict:
    rng = np.random.default_rng(seed)
    e_mtj = _logu(rng, 0.1, 10.0, n)
    p_gate = _logu(rng, 10.0, 100.0, n)
    e_cmos = _logu(rng, 5.0, 50.0, n)
    e_upd = _logu(rng, E_LEARN_LO_FJ, E_LEARN_HI_FJ, n)
    eps = _logu(rng, 0.005, 0.30, n)
    es = p_gate * 1e-9 * drive_time_s(mode, k) * 1e15 + e_cmos
    el = e_upd + ANGLE_CELLS * e_mtj
    f = 1.0 + CARNOT / eps
    at_1k = (es + u * el) * f
    at_300k = es * f + u * el
    ref = LOIHI_SOP_FJ + u * LOIHI_UPDATE_FJ
    return {
        "u": u, "n": n,
        "learn_share_median_1K": float(np.median(u * el / (es + u * el))),
        "wall_learn_at_1K_pJ_median": float(np.median(at_1k) / 1000),
        "wall_learn_at_300K_pJ_median": float(np.median(at_300k) / 1000),
        "sample_share_of_wall_300K_median": float(np.median(es * f / at_300k)),
        "loihi_reference_pJ": ref / 1000,
        "p_beats_loihi_learn_at_1K": float(np.mean(at_1k < ref)),
        "p_beats_loihi_learn_at_300K": float(np.mean(at_300k < ref)),
    }


if __name__ == "__main__":
    for m in ("hold", "reprep"):
        r = sample(mode=m)
        print(m, {k: v for k, v in r.items() if not k.startswith("_")})
