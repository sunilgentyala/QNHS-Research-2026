"""
Extended experiments: noise, network learning, energy uncertainty, security.

Writes every number used in the analysis to results/extended_results.json.

  E1  re-preparation noise: baseline, T2 / 2-qubit error / gate-time sweeps, k sweep
  E2  network learning with five synapse models (5 seeds) and a drive sweep
  E3  Monte Carlo energy uncertainty (hold and re-preparation modes)
  E4  Q-STDP poisoning: attack effect, rate-limit defense, detection power
  E5  MTJ TRNG current-precision window versus temperature

Usage: python run_extended_experiments.py [--quick]
"""

import json
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
os.chdir(REPO)
sys.path.insert(0, REPO)

from simulations import energy_uncertainty, mtj_trng, poisoning                 # noqa: E402
from simulations.network_learning import NetConfig, run as net_run             # noqa: E402
from simulations.reprep_noise import NoiseModel, evaluate, prep_duration_ns    # noqa: E402

QUICK = "--quick" in sys.argv


def e1():
    out = {"baseline": {}, "k_sweep": {}, "T2_sweep": [], "p2_sweep": [], "t2q_sweep": []}
    n = 20 if QUICK else 60
    for name, nm in (("ideal", NoiseModel.ideal()), ("hot", NoiseModel.hot_qubit()),
                     ("millikelvin", NoiseModel.millikelvin()),
                     ("hot_p1_exact", NoiseModel(p1=0.021, p2=0.03, T2_us=2.0, readout=0.02)),
                     ("huang_1K", NoiseModel.huang_1k()),
                     ("huang_1K_T2star", NoiseModel.huang_1k(with_T2star=True))):
        r = evaluate(nm, k=4, n=n)
        r["prep_ns"] = prep_duration_ns(4, nm)
        out["baseline"][name] = r
    for k in (1, 2, 3, 4):
        r = evaluate(NoiseModel.hot_qubit(), k=k, n=n)
        r["prep_ns"] = prep_duration_ns(k, NoiseModel.hot_qubit())
        out["k_sweep"][k] = r
    out["k_sweep_huang_1K"] = {k: evaluate(NoiseModel.huang_1k(), k=k, n=n) for k in (1, 2, 3, 4)}
    for T2 in np.logspace(np.log10(0.5), np.log10(2000), 12):
        only = evaluate(NoiseModel(T2_us=T2), k=4, n=n)
        full = evaluate(NoiseModel(p1=0.014, p2=0.03, T2_us=T2, readout=0.02), k=4, n=n)
        out["T2_sweep"].append({"T2_us": float(T2), "tvd_dephasing_only": only["tvd_mean"],
                                "tvd_with_gate_readout": full["tvd_mean"]})
    for p2 in np.logspace(-3, -1, 9):
        r = evaluate(NoiseModel(p2=p2), k=4, n=n)
        out["p2_sweep"].append({"p2": float(p2), "tvd": r["tvd_mean"], "dw": r["dw_mean"]})
    for t2q in (50.0, 100.0, 200.0, 500.0):
        nm = NoiseModel(p1=0.014, p2=0.03, T2_us=2.0, readout=0.02, t2q_ns=t2q)
        r = evaluate(nm, k=4, n=n)
        out["t2q_sweep"].append({"t2q_ns": t2q, "prep_ns": prep_duration_ns(4, nm), "tvd": r["tvd_mean"]})
    return out


def e2():
    seeds = range(2 if QUICK else 5)
    T = 60.0 if QUICK else 200.0
    models = ("classical", "qstdp_mean", "qstdp_ideal", "qstdp_hot", "qstdp_mk")
    main = {}
    for m in models:
        runs = [net_run(m, NetConfig(T_s=T, g=0.2), seed=s) for s in seeds]
        main[m] = {
            "selectivity_mean": float(np.mean([r["selectivity"] for r in runs])),
            "selectivity_std": float(np.std([r["selectivity"] for r in runs])),
            "w_corr_mean": float(np.mean([r["w_corr"] for r in runs])),
            "w_uncorr_mean": float(np.mean([r["w_uncorr"] for r in runs])),
            "post_rate_hz_mean": float(np.mean([r["post_rate_hz"] for r in runs])),
            "entropy_corr_mean": float(np.mean([r["entropy_corr"] for r in runs])),
            "entropy_uncorr_mean": float(np.mean([r["entropy_uncorr"] for r in runs])),
            "trace_mean": list(np.mean([r["selectivity_trace"] for r in runs], axis=0)),
        }
    drive = {}
    for g in (0.15, 0.2, 0.25, 0.3, 0.35):
        drive[g] = {}
        for m in ("classical", "qstdp_mean"):
            runs = [net_run(m, NetConfig(T_s=T, g=g), seed=s) for s in range(3)]
            drive[g][m] = {"selectivity_mean": float(np.mean([r["selectivity"] for r in runs])),
                           "post_rate_hz_mean": float(np.mean([r["post_rate_hz"] for r in runs]))}
    return {"seeds": len(list(seeds)), "T_s": T, "g": 0.2, "main": main, "drive_sweep": drive}


def e3():
    out = {"point_fJ": {m: energy_uncertainty.point_energy_fJ(m) for m in ("hold", "reprep")}}
    for mode in ("hold", "reprep"):
        r = energy_uncertainty.sample(mode=mode, n=20_000 if QUICK else 200_000)
        out[mode] = {k: v for k, v in r.items() if not k.startswith("_")}
    return out


def e4():
    fs = (0.0, 0.01, 0.02, 0.05, 0.1, 0.2)
    seeds = 5 if QUICK else 20
    none = poisoning.attack_effect(fs, clip=None, seeds=seeds)
    clip = poisoning.attack_effect(fs, clip=0.0005, seeds=seeds)
    det = {W: {f: poisoning.detection_power(f, window=W) for f in fs} for W in (200, 500, 1000)}
    return {"n_events": 2000, "attack_dt_ms": 5.0,
            "no_defense": {str(f): v for f, v in none.items()},
            "clip_0.0005": {str(f): v for f, v in clip.items()},
            "detection_power": {str(W): {str(f): p for f, p in d.items()} for W, d in det.items()}}


def e5():
    return [mtj_trng.window(T) for T in (300.0, 77.0, 20.0, 4.0, 1.0)]


if __name__ == "__main__":
    results = {"quick": QUICK}
    for name, fn in (("E1_reprep_noise", e1), ("E2_network_learning", e2), ("E3_energy_uncertainty", e3),
                     ("E4_poisoning", e4), ("E5_mtj_trng", e5)):
        t0 = time.time()
        results[name] = fn()
        print(f"{name} done in {time.time() - t0:.1f} s", flush=True)
    os.makedirs("results", exist_ok=True)
    with open("results/extended_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
    print("wrote results/extended_results.json")
