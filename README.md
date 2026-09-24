<div align="center">

# QNHS: Quantum-Neuromorphic Hybrid Substrate

### Open models for a nanoscale spin-qubit + spintronic + cryo-CMOS neuromorphic substrate, and an honest check of whether it can work

[![CI](https://github.com/sunilgentyala/QNHS-Research-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/sunilgentyala/QNHS-Research-2026/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sunilgentyala/QNHS-Research-2026?color=6c5ce7)](https://github.com/sunilgentyala/QNHS-Research-2026/releases)
[![Tests](https://img.shields.io/badge/tests-75%20passing-2ea44f)](tests/results/test_results.txt)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](requirements.txt)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Website](https://img.shields.io/badge/website-live-00b894)](https://sunilgentyala.github.io/QNHS-Research-2026/)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0005--2642--3479-a6ce39?logo=orcid&logoColor=white)](https://orcid.org/0009-0005-2642-3479)

**[Website](https://sunilgentyala.github.io/QNHS-Research-2026/)** ·
**[Quick Start](#quick-start)** ·
**[Results](#results)** ·
**[Threat Model](security/threat_model.md)** ·
**[Cite](#citation)**

</div>

---

Simulation code, unit tests, references and a hardware security threat model for **QNHS**, a proposed
monolithic three-plane architecture that stacks spin qubits, spintronic synapses and cryo-CMOS
control into one device. The code computes the energy, learning, device and error-correction numbers
so they can be checked rather than taken on trust, including the numbers that count against the idea.

> All QNHS figures are **theoretical projections** from the models in this repository, not measurements
> of fabricated hardware.

## At a glance

| | |
|---|---|
| **~11.1 fJ** | modeled energy per synaptic event (device level) |
| **≥3.3 pJ** | wall-plug energy per event once the Carnot cost of cooling 1 K to 300 K is charged (only ~3x under a 10 pJ GPU reference, even with an ideal refrigerator) |
| **33%** | refrigerator efficiency (fraction of Carnot) needed just to break even with the GPU reference |
| **2^k states** | weight distribution per synapse with k qubits (16 states for k = 4) |
| **~2 µs** | coherence demonstrated for silicon qubits above 1 K (Yang et al., Nature 2020), versus a 10 ms spike window: the main open gap |
| **75 / 75** | unit tests passing |

## Architecture

```
          ┌─────────────────────────────────────────────┐
 Plane 1  │  QCPP  Quantum Coherent Processing Plane    │  28Si spin qubit arrays, d=3 surface code
          ├──────────────── Cu-Cu bond, 200 nm pitch ───┤
 Plane 2  │  SSP   Spintronic Synaptic Plane            │  PMA-MTJ memristors, 4 states (2 bit)
          ├──────────────── Cu-Cu bond, 200 nm pitch ───┤
 Plane 3  │  CPP   CMOS Peripheral Plane                │  3 nm cryo-CMOS FinFET: LIF neurons, MWPM decoder
          └─────────────────────────────────────────────┘
                              operated at ~1 K
```

## Key contributions

1. **Three-plane monolithic architecture.** Quantum, spintronic and CMOS planes joined by hybrid bonding (200 nm pitch is a design target).
2. **Quantum synaptic encoding.** Each synapse is a k-qubit state in a 2^k-dimensional Hilbert space, so the weight is a distribution with built-in Bayesian uncertainty.
3. **Q-STDP learning rule.** Spike-timing-dependent plasticity in the amplitude domain. LTP moves probability mass toward higher-weight basis states and LTD moves it toward lower ones.
4. **Error-correction and coherence budget.** d = 3 gives a 10x gain at 0.1% physical error but none at the ~1% error rates measured above 1 K, so holding amplitudes for a 10 ms spike window is out of reach today.
5. **Energy model with cooling.** 11.1 fJ per event at the device, at least 3.3 pJ at the wall plug once the Carnot cost of 1 K operation is charged.
6. **Hardware security analysis.** Side-channel, learning-rule poisoning, Trojan and supply-chain threats, plus candidate primitives (quantum-dot PUFs, MTJ random-number generation).

## Quick start

```bash
git clone https://github.com/sunilgentyala/QNHS-Research-2026.git
cd QNHS-Research-2026
pip install -r requirements.txt

python run_all_simulations.py     # all four models + tests + figures/*.png
python -m pytest tests/ -v        # 75 unit tests
```

Each model also runs on its own, from any directory:

```bash
python simulations/energy_model.py
python simulations/qstdp_simulation.py
python simulations/mtj_resistance_model.py
python simulations/surface_code_analysis.py
```

## Results

### 1. Energy per synaptic event

<img src="docs/assets/energy_comparison.png" alt="Synaptic energy comparison: H100, Loihi 2, NorthPole, QNHS" width="720">

| Component | Value | Basis |
|-----------|------:|-------|
| E_MTJ | 0.10 fJ | SOT switching, 20 nm PMA-MTJ, 1 ns pulse |
| E_qubit | 0.99 fJ | 30 nW gate drive, 33 ns pi-pulse (30 MHz Rabi) |
| E_CMOS | 10.0 fJ | LIF neuron + MWPM + SerDes, 3 nm FinFET at 1 K |
| **E_syn** | **11.09 fJ** | **sum; roughly 900x below the ~10 pJ H100 figure** |

### 2. Q-STDP learning dynamics

<img src="docs/assets/qstdp_dynamics.png" alt="Q-STDP mean weight, entropy, kernel and final distribution" width="720">

```
alpha_l(t+1) = N[ alpha_l(t) + eta * K(dt) * (w_l - <w>) * alpha_l(t) ]
K(dt)        = A+ exp(-dt/tau+) Theta(dt)  -  A- exp(dt/tau-) Theta(-dt)
```

Under sustained potentiation (dt = +15 ms, 200 events) the mean weight rises from 0.40 to 0.59.
Under sustained depression (dt = -15 ms) it falls to 0.25.

### 3. PMA-MTJ synaptic device

<img src="docs/assets/mtj_characteristics.png" alt="MTJ resistance states, switching probability and crossbar map" width="720">

Four resistance states (5.0 / 8.3 / 11.7 / 15.0 kΩ) encode 2 bits per synapse, with TMR = 200% and a 60 k_B T retention barrier.

### 4. Surface code error suppression

<img src="docs/assets/surface_code_scaling.png" alt="Logical error rate and coherence enhancement vs. code distance" width="720">

`p_L = p_phys (p_phys / p_th)^((d-1)/2)`. At p_phys = 0.1% and d = 3 this gives p_L = 1e-4 and a 10x coherence gain.
The 1 µs MWPM decoder cycle fits 10,000 times into a 10 ms spike window.

### Comparison

| Metric | NVIDIA H100 | Intel Loihi 2 | IBM NorthPole | QNHS (projected) |
|--------|-------------|---------------|---------------|------------------|
| Energy evidence | ~10 pJ/event (reference) | measured chips | 25x FPS/W vs 12 nm GPU | **11.1 fJ device, ≥3.3 pJ wall-plug** |
| Weight encoding | FP16 | INT8 | INT8 | **2^k quantum states** |
| Bayesian uncertainty | None | None | None | **Intrinsic** |
| Spike-native | No | Yes | Partial | **Yes** |
| Security primitives | None | None | None | **PUF, TRNG (proposed)** |
| Operating temperature | 300 K | 300 K | 300 K | **~1 K** |

The QNHS wall-plug figure charges the Carnot minimum of 299 J of work per joule removed at 1 K. Real refrigerators do worse, which raises the cost further (see `refrigeration_overhead(fraction_of_carnot=...)`).

## Repository structure

```
QNHS-Research-2026/
├── run_all_simulations.py       # one-command runner: models, tests, figures
├── simulations/
│   ├── energy_model.py          # synaptic energy decomposition
│   ├── qstdp_simulation.py      # Q-STDP amplitude learning
│   ├── mtj_resistance_model.py  # PMA-MTJ four-state model
│   └── surface_code_analysis.py # distance-d surface code coherence
├── tests/                       # 75 unit tests + results/ snapshots
├── references/references.bib    # 15 references, each checked against Crossref
├── security/threat_model.md     # hardware security threat model
├── docs/                        # GitHub Pages website
└── figures/                     # generated by the runner (git-ignored)
```

The manuscript itself is kept out of this repository.

## Security

The threat model covers:

- **Side channels.** Lu et al. (GLSVLSI 2025, [10.1145/3716368.3735264](https://doi.org/10.1145/3716368.3735264)) fingerprinted cloud quantum hardware in 10 queries. Choudhury et al. (NDSS 2025, [10.14722/ndss.2025.242185](https://doi.org/10.14722/ndss.2025.242185)) used crosstalk to identify a victim's quantum algorithm with up to 85.7% accuracy.
- **Adversarial weights.** Projective sampling makes inference stochastic, but stochastic defenses can be bypassed by gradient averaging, so no robustness is claimed without evaluation. Q-STDP opens a training-time poisoning channel; update clipping and spike-statistics monitoring are candidate defenses.
- **Primitives.** Quantum-dot PUFs from charge-noise signatures and MTJ random-number generation (thermal switching is strongly suppressed at 1 K, so this needs near-critical biasing or low-barrier cells). Crossbar acceleration of lattice PQC is a research direction only: ML-KEM needs exact mod-3329 arithmetic that 2-bit analog cells cannot supply directly.
- **Supply chain.** Trusted-foundry flow and post-fabrication verification at 1 K for cryo-CMOS logic locking.

Full document: [security/threat_model.md](security/threat_model.md)

## Citation

```bibtex
@software{gentyala2026qnhs,
  author = {Gentyala, Sunil},
  title  = {{QNHS}: Quantum-Neuromorphic Hybrid Substrate simulation suite},
  year   = {2026},
  url    = {https://github.com/sunilgentyala/QNHS-Research-2026}
}
```

GitHub's **"Cite this repository"** button reads [CITATION.cff](CITATION.cff).

## Author

**Sunil Gentyala**, IEEE Senior Member
Independent Researcher, HCLTech (HCL America Inc.), Dallas, TX, USA
[sunil.gentyala@ieee.org](mailto:sunil.gentyala@ieee.org) ·
[ORCID](https://orcid.org/0009-0005-2642-3479) ·
[LinkedIn](https://www.linkedin.com/in/sunil-gentyala) ·
[GitHub](https://github.com/sunilgentyala)

## License

MIT. See [LICENSE](LICENSE).
