# Entangled Intelligence: Nanoscale Quantum-Neuromorphic Hybrid Architectures for Post-von Neumann Computation

**GitHub Repository:** https://github.com/sunilgentyala/QNHS-Research-2026

**Author:** Sunil Gentyala
**Affiliation:** Independent Researcher, HCLTech (HCL America Inc.), Dallas, TX 75001, USA
**Email:** sunil.gentyala@ieee.org
**ORCID:** [0009-0005-2642-3479](https://orcid.org/0009-0005-2642-3479)
**IEEE Senior Member**

---

## Overview

This repository contains open-source simulation code, test suites, references, and a security threat model accompanying the research paper:

> **"Entangled Intelligence: Nanoscale Quantum-Neuromorphic Hybrid Architectures for Post-von Neumann Computation"**
> Sunil Gentyala
> Under review for conference submission, 2026

The paper proposes and analyzes the **Quantum-Neuromorphic Hybrid Substrate (QNHS)**: a vertically integrated monolithic architecture co-integrating:

- **28Si spin qubit arrays** -- Quantum Coherent Processing Plane (QCPP)
- **PMA-MTJ spintronic memristors** -- Spintronic Synaptic Plane (SSP)
- **3 nm cryo-CMOS FinFET circuits** -- CMOS Peripheral Plane (CPP)

The architecture projects **~11 fJ per synaptic event** (three orders of magnitude below GPU baselines) with intrinsic Bayesian uncertainty quantification and hardware-native security primitives.

---

## Key Contributions

1. **QNHS Three-Plane Architecture** -- Monolithic vertical integration of quantum, spintronic, and CMOS planes bonded via Cu-Cu thermocompression at 200 nm pitch.

2. **Quantum Synaptic Encoding** -- Each synapse encoded as a k-qubit quantum state in a 2^k-dimensional Hilbert space, providing intrinsic Bayesian weight distributions.

3. **Q-STDP Learning Rule** -- Quantum amplitude-domain spike-timing-dependent plasticity that reproduces Hebbian learning while encoding probabilistic weight distributions.

4. **Distance-3 Surface Code Protection** -- Topological error correction at 1 K projecting logical coherence lifetimes of up to 100 ms across multiple spike integration windows.

5. **First Security Analysis for Quantum-Neuromorphic Hardware** -- Covers side-channel attacks (GLSVLSI 2025, NDSS 2025), adversarial weight manipulation, hardware trojans, and supply chain threats.

6. **Hardware Security Primitives** -- Quantum dot physical unclonable functions (QD-PUFs), MTJ true random number generation (QRNG), and post-quantum cryptography acceleration via the analog MTJ crossbar.

---

## Repository Structure

```
QNHS-Research-2026/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── generate_papers.py          # Venue-neutral DOCX generator (IEEE + ACM formats)
├── run_all_simulations.py      # One-command full suite runner with summary report
├── simulations/
│   ├── __init__.py
│   ├── energy_model.py         # QNHS synaptic energy decomposition (Eq. 3)
│   ├── qstdp_simulation.py     # Q-STDP quantum amplitude learning simulation
│   ├── mtj_resistance_model.py # PMA-MTJ four-state resistance modeling
│   └── surface_code_analysis.py# Distance-3 surface code coherence analysis
├── tests/
│   ├── __init__.py
│   ├── test_energy_model.py    # 14 unit tests -- energy decomposition
│   ├── test_qstdp.py           # 21 unit tests -- Q-STDP learning rule
│   ├── test_mtj_model.py       # 22 unit tests -- MTJ resistance model
│   ├── test_surface_code.py    # 15 unit tests -- surface code analysis
│   └── results/
│       ├── test_results.txt    # 72/72 passed (pytest output)
│       └── simulation_summary.txt  # Numerical results snapshot
├── references/
│   └── references.bib          # 26 BibTeX entries (all DOIs verified May 2026)
├── security/
│   └── threat_model.md         # Full QNHS hardware security threat model
└── figures/                    # Populated by running simulation scripts
```

> **Note:** Paper DOCX files (IEEE and ACM formats) are kept separately and not tracked in this repository. Run `python generate_papers.py` to regenerate them locally.

---

## Quick Start

```bash
git clone https://github.com/sunilgentyala/QNHS-Research-2026.git
cd QNHS-Research-2026
pip install -r requirements.txt
python run_all_simulations.py
```

To run the full test suite:

```bash
python -m pytest tests/ -v
```

---

## Simulation Modules

### 1. Energy Model (`simulations/energy_model.py`)

Implements the three-component synaptic energy decomposition (Eq. 3 in paper):

| Component | Value | Source |
|-----------|-------|--------|
| E_MTJ | 0.1 fJ | SOT switching, 20 nm PMA-MTJ, 1 ns pulse |
| E_qubit | ~1 fJ | 30 nW gate drive, 33 ns pi-pulse (30 MHz Rabi) |
| E_CMOS | 10 fJ | LIF neuron + MWPM + SerDes, 3 nm FinFET at 1 K |
| **E_syn** | **~11 fJ** | **Total -- ~3 orders below NVIDIA H100** |

```bash
python simulations/energy_model.py
```

### 2. Q-STDP Simulation (`simulations/qstdp_simulation.py`)

Simulates quantum spike-timing-dependent plasticity on a single k-qubit synapse:

- Amplitude update rule: `alpha_l^(t+1) = N[ alpha_l + eta * K(dt) * alpha_l ]`
- Tracks weight distribution evolution, Shannon entropy, and LTP/LTD dynamics
- Demonstrates Bayesian uncertainty quantification absent in classical neuromorphic systems

```bash
python simulations/qstdp_simulation.py
```

### 3. MTJ Resistance Model (`simulations/mtj_resistance_model.py`)

Models PMA-MTJ spintronic synaptic device characteristics:

- Four resistance states {R0, R1, R2, R3} encoding 2 bits per synapse
- TMR ratio >200%, retention barrier 60 k_B T
- Neel-Brown thermally activated switching (sub-critical J) and deterministic SOT switching (J >= J_c)

```bash
python simulations/mtj_resistance_model.py
```

### 4. Surface Code Analysis (`simulations/surface_code_analysis.py`)

Analyzes distance-3 surface code topological protection for spin qubits at 1 K:

- Logical error rate: `p_L = p_phys * (p_phys / p_th)^((d-1)/2)`
- Coherence enhancement: 10x at current 28Si fidelity, 50x with isotopic enrichment roadmap
- MWPM decoder latency (1 us) verified << spike integration window (10 ms)

```bash
python simulations/surface_code_analysis.py
```

---

## Test Results

72 unit tests across four modules, all passing:

```
tests/test_energy_model.py    14 passed
tests/test_mtj_model.py       22 passed
tests/test_qstdp.py           21 passed
tests/test_surface_code.py    15 passed
------------------------------------------
TOTAL                         72 passed
```

Full output: [`tests/results/test_results.txt`](tests/results/test_results.txt)

---

## Key Results Summary

| Metric | NVIDIA H100 | Intel Loihi 2 | IBM NorthPole | QNHS (Projected) |
|--------|-------------|---------------|---------------|------------------|
| E_syn (device level) | ~10 pJ | ~1 pJ | ~0.5 pJ | **~11 fJ** |
| Wall-plug efficiency vs H100 | 1x baseline | ~10x | ~20x | **~20x** |
| Weight encoding | FP16 | INT8 | INT8 | **2^k quantum states** |
| Bayesian uncertainty | None | None | None | **Intrinsic** |
| Spike-native processing | No | Yes | Partial | **Yes** |
| Hardware security primitives | None | None | None | **PUF + QRNG + PQC** |
| Operating temperature | 300 K | 300 K | 300 K | **~1 K** |

Wall-plug efficiency accounts for ~50x Carnot refrigeration overhead at 1 K from 300 K. QNHS figures are theoretical projections; all other figures are from published specifications.

---

## Security Contributions

This paper provides the first comprehensive security analysis for a quantum-neuromorphic hardware substrate:

- **Side-channel attacks**: Lu et al. (GLSVLSI 2025, DOI: 10.1145/3716368.3735264) demonstrated 10-query hardware fingerprinting on cloud quantum services; Choudhury et al. (NDSS 2025, arXiv:2412.10507) showed 85.7% circuit reconstruction via crosstalk.
- **Adversarial robustness**: Quantum amplitude encoding provides inherent stochastic resilience against gradient-based attacks; Q-STDP training-phase poisoning countered via differential privacy.
- **Hardware security primitives**: QD-PUFs from charge noise signatures, MTJ-QRNG from stochastic free-layer switching, and crossbar-based PQC acceleration for NIST FIPS 203/204/205 lattice schemes.
- **Supply chain**: Trusted foundry and post-fabrication 1 K verification requirements for cryo-CMOS logic encryption.

Full threat model: [security/threat_model.md](security/threat_model.md)

---

## References

All 26 references are compiled in [`references/references.bib`](references/references.bib) with verified DOIs. Key 2024-2025 additions include:

- Mills et al., Nature 646, 81-87 (2025) -- 99% fidelity in 300 mm foundry. DOI: 10.1038/s41586-025-09531-9
- Simmons et al., Nature 648, 569-575 (2025) -- 11-qubit atom processor. DOI: 10.1038/s41586-025-09827-w
- Lu et al., GLSVLSI 2025 -- quantum timing side-channel. DOI: 10.1145/3716368.3735264
- Choudhury et al., NDSS 2025 -- crosstalk-based circuit reconstruction. arXiv:2412.10507
- NIST FIPS 203/204/205, Aug. 2024 -- post-quantum cryptography standards

---

## Citation

If you use this code or reference this work, please cite (update venue when published):

```bibtex
@inproceedings{gentyala2026qnhs,
  author    = {Gentyala, Sunil},
  title     = {Entangled Intelligence: Nanoscale Quantum-Neuromorphic Hybrid
               Architectures for Post-von Neumann Computation},
  booktitle = {Proceedings of [Conference Name]},
  year      = {2026},
  note      = {GitHub: https://github.com/sunilgentyala/QNHS-Research-2026}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Contact

**Sunil Gentyala**
Independent Researcher | HCLTech (HCL America Inc.), Dallas, TX 75001, USA
Email: sunil.gentyala@ieee.org
ORCID: 0009-0005-2642-3479
LinkedIn: linkedin.com/in/sunilgentyala
GitHub: github.com/sunilgentyala
