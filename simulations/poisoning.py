"""
Training-time poisoning of a Q-STDP synapse, and two defenses.

Benign traffic: spike pairs with dt uniform in [-50, 50] ms.
Attack: a fraction f of pairs is replaced by attacker-timed pairs at
dt = +5 ms, which potentiate the synapse on every event.

Defenses evaluated:
  clip    : bound the change in mean weight per update to c (rate limiting)
  detect  : one-sided binomial test on the share of pairs with dt in (0, 10] ms
            over a window of W pairs (benign share = 0.10)
"""

import numpy as np
from math import comb

BASIS = np.linspace(0.0, 1.0, 16)


def kernel(dt, A_plus=0.20, A_minus=0.21, tau=20.0):
    return np.where(dt > 0, A_plus * np.exp(-dt / tau), np.where(dt < 0, -A_minus * np.exp(dt / tau), 0.0))


def _step(alpha, dt, eta=0.05, clip=None):
    p = alpha ** 2
    mean = p @ BASIS
    a = alpha + eta * float(kernel(dt)) * (BASIS - mean) * alpha
    a /= np.linalg.norm(a)
    if clip is not None:
        new_mean = (a ** 2) @ BASIS
        d = new_mean - mean
        if abs(d) > clip:
            # shrink the step until the mean moves by at most `clip`
            lo, hi = 0.0, 1.0
            for _ in range(30):
                s = 0.5 * (lo + hi)
                b = alpha + s * eta * float(kernel(dt)) * (BASIS - mean) * alpha
                b /= np.linalg.norm(b)
                if abs((b ** 2) @ BASIS - mean) > clip:
                    hi = s
                else:
                    lo = s
            a = alpha + lo * eta * float(kernel(dt)) * (BASIS - mean) * alpha
            a /= np.linalg.norm(a)
    return a


def run(f: float, n_events: int = 2000, clip=None, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    alpha = np.sqrt(np.random.default_rng(10_000 + seed).dirichlet(np.ones(16)))
    for _ in range(n_events):
        dt = 5.0 if rng.random() < f else rng.uniform(-50, 50)
        if dt == 0:
            continue
        alpha = _step(alpha, dt, clip=clip)
    return float((alpha ** 2) @ BASIS)


def attack_effect(fs=(0.0, 0.02, 0.05, 0.1, 0.2), clip=None, seeds=20, n_events=2000) -> dict:
    out = {}
    for f in fs:
        vals = [run(f, n_events, clip, s) for s in range(seeds)]
        out[f] = (float(np.mean(vals)), float(np.std(vals)))
    return out


def detection_power(f: float, window: int = 200, alpha_level: float = 0.01,
                    base: float = 0.10, trials: int = 5000, seed: int = 0) -> float:
    """Probability that a one-sided binomial test flags a window with attack share f."""
    # critical count: smallest c with P(X >= c | base) <= alpha_level
    tail = 0.0
    crit = window + 1
    for c in range(window, -1, -1):
        tail += comb(window, c) * base ** c * (1 - base) ** (window - c)
        if tail > alpha_level:
            crit = c + 1
            break
    rng = np.random.default_rng(seed)
    p_hit = f + (1 - f) * base          # attack pairs always fall in (0, 10] ms
    hits = rng.binomial(window, p_hit, size=trials)
    return float(np.mean(hits >= crit))


if __name__ == "__main__":
    print("no defense", attack_effect(seeds=5))
    print("clip 0.002", attack_effect(clip=0.002, seeds=5))
    for f in (0.02, 0.05, 0.1):
        print(f, detection_power(f))
