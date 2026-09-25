"""
Shared, time-multiplexed quantum sampling engines for re-preparation mode.

In re-preparation mode the quantum register is a transient resource: it is
prepared, measured and reset for each synaptic event, while the synaptic
distributions stay in classical (MTJ/CMOS) memory. A register therefore does not
need to belong to one synapse. A pool of c engines, each with k qubits, can
serve a whole crossbar if it keeps up with the event rate.

Model: synaptic events arrive as a Poisson stream of rate lam (events/s); each
event occupies an engine for tau seconds (initialization + gates + readout).
We size the pool with the Erlang C formula of an M/M/c queue, which is
conservative for deterministic service times, and report the smallest c for
which the probability that an event must wait is below a target.
"""

from dataclasses import dataclass
import math


def erlang_c(c: int, a: float) -> float:
    """Probability of waiting in an M/M/c queue with offered load a = lam * tau."""
    if c <= a:
        return 1.0
    inv_b = 1.0                      # Erlang B by recursion, numerically stable
    for j in range(1, c + 1):
        inv_b = 1.0 + inv_b * j / a
    b = 1.0 / inv_b
    rho = a / c
    return b / (1.0 - rho + rho * b)


def mean_wait_s(c: int, a: float, tau: float) -> float:
    if c <= a:
        return math.inf
    return erlang_c(c, a) * tau / (c - a)


@dataclass
class PoolResult:
    events_per_s: float
    tau_s: float
    offered_load: float
    engines: int
    qubits: int
    dedicated_qubits: int
    p_wait: float
    mean_wait_us: float
    utilization: float


def size_pool(n_synapses: int, rate_hz: float, k: int, tau_s: float,
              p_wait_target: float = 0.01) -> PoolResult:
    lam = n_synapses * rate_hz
    a = lam * tau_s
    c = max(1, math.floor(a) + 1)
    while erlang_c(c, a) > p_wait_target:
        c += 1
    return PoolResult(events_per_s=lam, tau_s=tau_s, offered_load=a, engines=c, qubits=c * k,
                      dedicated_qubits=n_synapses * k, p_wait=erlang_c(c, a),
                      mean_wait_us=mean_wait_s(c, a, tau_s) * 1e6, utilization=a / c)


# Event service times. The 1 K value uses the ~150 us algorithmic initialization
# and 50 us readout integration reported by Huang et al. (2024) plus the gate
# time of the loading circuit; the "fast" value assumes initialization and
# readout of about 1 us each, a target rather than a demonstrated figure.
def service_time_s(k: int, init_s: float = 150e-6, readout_s: float = 50e-6,
                   t1q: float = 33e-9, t2q: float = 100e-9) -> float:
    gates = (2 ** k - 1) * t1q + (2 ** k - 2) * t2q
    return init_s + gates + readout_s


if __name__ == "__main__":
    for n, k in ((256 * 256, 4), (64 * 64, 2)):
        for label, tau in (("1K_measured", service_time_s(k)),
                           ("fast_target", service_time_s(k, 1e-6, 1e-6))):
            print(n, k, label, size_pool(n, 10.0, k, tau))
