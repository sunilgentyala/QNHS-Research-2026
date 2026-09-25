"""
Network-level learning with Q-STDP synapses.

A single leaky integrate-and-fire (LIF) neuron receives N Poisson inputs at the
same rate. Half of them share a common source, so their spikes are correlated.
Competitive STDP should strengthen the correlated group and weaken the rest
(the standard Song-Miller-Abbott setting). We compare these synapse models:

  classical   : additive STDP on a scalar weight in [0, 1]
  mult        : multiplicative (soft-bound) STDP on a scalar weight,
                dw = eta_m K (1 - w) for K > 0 and dw = eta_m K w for K < 0
                (the mu = 1 limit of Gutig et al. 2003)
  vanrossum   : additive potentiation, multiplicative depression
                (van Rossum, Bi and Turrigiano 2000),
                dw = eta K for K > 0 and dw = eta_d K w for K < 0
  qstdp_mean  : Q-STDP amplitude update, but the synapse transmits <w>
                (no sampling; isolates the effect of sampling noise)
  qstdp_ideal : Q-STDP, each presynaptic spike transmits a weight sampled
                from the ideal distribution |alpha_l|^2
  qstdp_hot   : as qstdp_ideal, but the sample comes from the distribution
                measured after noisy re-preparation at ~1.5 K
  qstdp_mk    : as qstdp_hot with millikelvin noise parameters
  qstdp_huang : as qstdp_hot with the 1 K benchmark noise case (Huang et al. 2024)

Because the synapses are never entangled with each other, qstdp_ideal is
equivalent in distribution to a classical stochastic synapse that stores the
same probabilities. The experiment therefore measures how sampling itself, and
hardware noise on top of it, affect learning.

Selectivity = mean weight of correlated inputs - mean weight of uncorrelated
inputs, where the weight is <w> for Q-STDP synapses.
"""

from dataclasses import dataclass

import numpy as np

from simulations.reprep_noise import NoiseModel, simulate_distribution


@dataclass
class NetConfig:
    n_inputs: int = 20
    rate_hz: float = 10.0
    corr_fraction: float = 0.5      # share of a correlated input's spikes from the common source
    T_s: float = 100.0
    dt_ms: float = 1.0
    tau_m_ms: float = 20.0
    v_th: float = 1.0
    g: float = 0.25                 # membrane jump per unit transmitted weight
    k: int = 4
    eta: float = 0.05
    A_plus: float = 0.20
    A_minus: float = 0.21
    tau_ms: float = 20.0
    eta_classical: float = 0.01
    eta_mult: float = 0.02          # matches the additive step at w = 0.5
    eta_vr_dep: float = 0.02        # van Rossum depression rate, matched at w = 0.5
    refresh: int = 5                # recompute noisy distribution every N spikes per synapse


SCALAR_MODELS = ("classical", "mult", "vanrossum")


def _inputs(cfg: NetConfig, rng: np.random.Generator) -> np.ndarray:
    steps = int(cfg.T_s * 1000 / cfg.dt_ms)
    p = cfg.rate_hz * cfg.dt_ms / 1000
    half = cfg.n_inputs // 2
    spikes = rng.random((steps, cfg.n_inputs)) < p
    common = rng.random(steps) < p
    take = rng.random((steps, half)) < cfg.corr_fraction
    spikes[:, :half] = np.where(take, common[:, None], rng.random((steps, half)) < p)
    return spikes


def _kernel(cfg: NetConfig, dt_ms: float) -> float:
    if dt_ms > 0:
        return cfg.A_plus * np.exp(-dt_ms / cfg.tau_ms)
    if dt_ms < 0:
        return -cfg.A_minus * np.exp(dt_ms / cfg.tau_ms)
    return 0.0


def run(model: str, cfg: NetConfig = NetConfig(), seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    spikes = _inputs(cfg, rng)
    steps, n = spikes.shape
    basis = np.linspace(0.0, 1.0, 2 ** cfg.k)
    init = np.random.default_rng(1000 + seed).dirichlet(np.ones(2 ** cfg.k), size=n)
    alpha = np.sqrt(init)                                   # Q-STDP amplitudes
    w_cl = (init * basis).sum(axis=1)                        # classical weights, same start
    scalar = model in SCALAR_MODELS
    noise = {"qstdp_hot": NoiseModel.hot_qubit(), "qstdp_mk": NoiseModel.millikelvin(),
             "qstdp_huang": NoiseModel.huang_1k()}.get(model)
    noisy = [None] * n
    since = np.full(n, 10 ** 9)

    def probs(i):
        return alpha[i] ** 2 / np.sum(alpha[i] ** 2)

    def update(i, dt):
        nonlocal n_updates
        K = _kernel(cfg, dt)
        if K == 0.0:
            return
        n_updates += 1
        if model == "classical":
            w_cl[i] = np.clip(w_cl[i] + cfg.eta_classical * K, 0.0, 1.0)
        elif model == "mult":
            f = (1.0 - w_cl[i]) if K > 0 else w_cl[i]
            w_cl[i] = np.clip(w_cl[i] + cfg.eta_mult * K * f, 0.0, 1.0)
        elif model == "vanrossum":
            dw = cfg.eta_classical * K if K > 0 else cfg.eta_vr_dep * K * w_cl[i]
            w_cl[i] = np.clip(w_cl[i] + dw, 0.0, 1.0)
        else:
            mean = float(np.dot(probs(i), basis))
            a = alpha[i] + cfg.eta * K * (basis - mean) * alpha[i]
            alpha[i] = a / np.linalg.norm(a)

    v = 0.0
    decay = np.exp(-cfg.dt_ms / cfg.tau_m_ms)
    last_pre = np.full(n, -1e9)
    last_post = -1e9
    n_post = 0
    n_updates = 0
    n_pre = 0
    trace_sel = []
    for t in range(steps):
        tm = t * cfg.dt_ms
        v *= decay
        for i in np.flatnonzero(spikes[t]):
            n_pre += 1
            if scalar:
                w = w_cl[i]
            elif model == "qstdp_mean":
                w = float(np.dot(probs(i), basis))
            else:
                if noise is None:
                    dist = probs(i)
                else:
                    if since[i] >= cfg.refresh:
                        noisy[i] = simulate_distribution(probs(i), noise)
                        since[i] = 0
                    since[i] += 1
                    dist = noisy[i]
                w = basis[rng.choice(len(basis), p=dist)]
            v += cfg.g * w
            update(i, last_post - tm)          # pre after post: depression
            last_pre[i] = tm
        if v >= cfg.v_th:
            v = 0.0
            last_post = tm
            n_post += 1
            for i in range(n):
                if tm - last_pre[i] < 5 * cfg.tau_ms:
                    # post after pre: potentiation. A presynaptic spike in the same
                    # time step caused this spike, so count it as causal (dt/2).
                    update(i, max(tm - last_pre[i], 0.5 * cfg.dt_ms))
        if t % 1000 == 0:
            w_now = w_cl if scalar else (alpha ** 2 / (alpha ** 2).sum(1, keepdims=True)) @ basis
            trace_sel.append(float(w_now[: n // 2].mean() - w_now[n // 2:].mean()))
    w_end = w_cl if scalar else (alpha ** 2 / (alpha ** 2).sum(1, keepdims=True)) @ basis
    p_end = alpha ** 2 / (alpha ** 2).sum(1, keepdims=True)
    ent = -(p_end * np.log2(np.clip(p_end, 1e-12, None))).sum(1)
    return {
        "model": model,
        "seed": seed,
        "selectivity": float(w_end[: n // 2].mean() - w_end[n // 2:].mean()),
        "w_corr": float(w_end[: n // 2].mean()),
        "w_uncorr": float(w_end[n // 2:].mean()),
        "post_rate_hz": n_post / cfg.T_s,
        "updates_per_pre_spike": n_updates / max(n_pre, 1),
        "entropy_corr": float(ent[: n // 2].mean()),
        "entropy_uncorr": float(ent[n // 2:].mean()),
        "selectivity_trace": trace_sel,
    }


if __name__ == "__main__":
    import time
    for m in ("classical", "qstdp_mean", "qstdp_ideal"):
        t0 = time.time()
        r = run(m, NetConfig(T_s=30.0))
        print(f"{m:12s} sel={r['selectivity']:+.3f} corr={r['w_corr']:.3f} uncorr={r['w_uncorr']:.3f} "
              f"post={r['post_rate_hz']:.1f} Hz  ({time.time()-t0:.1f}s)")
