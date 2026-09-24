"""
How precisely must the write current be set to use an MTJ as a true random
number generator (TRNG) at 1 K versus 300 K?

Uses the Neel-Brown model in mtj_resistance_model.MTJDevice: the barrier
E_b = 60 k_B (300 K) is reduced by the current as E_b (1 - J/Jc)^1.5 and a 1 ms
pulse switches with probability 1 - exp(-t / (tau0 exp(E/kT))).

For each temperature we find J50 (P = 0.5) and the current window in which
|P - 0.5| <= 0.01, expressed relative to J50.
"""

import numpy as np

from simulations.mtj_resistance_model import MTJDevice


def p_switch(j: float, temp_K: float) -> float:
    return MTJDevice(temp_K=temp_K).switching_probability(j)


def _solve(target: float, temp_K: float, lo=1e-6, hi=0.999999) -> float:
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if p_switch(mid, temp_K) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def window(temp_K: float, tol: float = 0.01) -> dict:
    j50 = _solve(0.5, temp_K)
    jl, jh = _solve(0.5 - tol, temp_K), _solve(0.5 + tol, temp_K)
    return {"temp_K": temp_K, "J50_over_Jc": j50, "window_rel": (jh - jl) / j50}


if __name__ == "__main__":
    for T in (300.0, 77.0, 4.0, 1.0):
        w = window(T)
        print(f"T={T:6.1f} K  J50/Jc={w['J50_over_Jc']:.5f}  relative window for P=0.5+-0.01: {w['window_rel']:.2e}")
