# QNHS Security Threat Model
## Quantum-Neuromorphic Hybrid Substrate (QNHS)
**Author:** Sunil Gentyala | ORCID: 0009-0005-2642-3479  
**Affiliation:** Independent Researcher, HCLTech (HCL America Inc.), Dallas, TX  
**Repository:** https://github.com/sunilgentyala/QNHS-Research-2026

---

## 1. Overview

The QNHS architecture introduces a novel and largely unexplored attack surface that combines
threats from quantum computing hardware, spintronic devices, cryogenic electronics, and
classical AI systems. This document catalogs known and projected threat vectors, assesses
their severity for QNHS deployments, and proposes countermeasures aligned with the
physical properties of the substrate.

---

## 2. Threat Categories

### 2.1 Side-Channel Attacks on Cryogenic Systems

**Threat:** Timing, power, and electromagnetic side-channels in the cryo-CMOS peripheral plane.

**Evidence (2025):**
- Lu et al. (GLSVLSI 2025, DOI: 10.1145/3716368.3735264) demonstrated that timing
  measurements with as few as **10 samples** can identify the underlying quantum hardware
  and subvert algorithm confidentiality on IBM cloud quantum services.
- Choudhury et al. (NDSS 2025, arXiv:2412.10507) showed that **crosstalk signatures**
  between adjacent qubits enable adversaries with minimal privileges to identify a victim's
  quantum algorithm with 85.7% accuracy across 336 benchmark circuits.

**QNHS-Specific Vectors:**
- RF pulse timing analysis of qubit control lines (Rabi frequency signatures at 30 MHz)
- MTJ switching noise leaking through dilution refrigerator wiring
- MWPM decoder access latency variations correlating with syndrome patterns
- Thermal fluctuations in superfluid-He cooling channels detectable as pressure signals

**Severity:** HIGH for cloud/multi-tenant deployments; MEDIUM for dedicated hardware.

**Countermeasures:**
- Constant-time MWPM decoder scheduling (randomize idle cycles)
- Electromagnetic shielding of qubit control lines within the cryostat
- Noise injection on power rails feeding the cryo-CMOS SerDes I/O
- Physical isolation of timing references from user-observable channels

---

### 2.2 Adversarial Attacks on Quantum-Encoded Weights

**Threat:** Deliberate manipulation of quantum amplitude distributions to corrupt inference.

**Evidence (2024-2025):**
- Yocam et al. (arXiv:2412.12373) identified backdoor attacks via quantum state-universal
  adversarial perturbations (QS-UAP) that can corrupt quantum neural network outputs
  while remaining undetectable to classical verification.
- Scoping review (Computers 2025, MDPI) of 53 empirical studies confirms that input-level
  evasion attacks against variational quantum circuits are practical on NISQ hardware.

**QNHS-Specific Vectors:**
- Manipulating presynaptic spike timing (dt in Q-STDP) to bias amplitude distributions
- Injecting spurious syndrome errors into the MWPM decoder to corrupt logical qubits
- Exploiting the MTJ write path (SOT current) to force incorrect resistance states
- Attacking the Q-STDP amplitude update equation by controlling spike-pair statistics

**Partial Mitigation from Architecture:**
- Quantum amplitude encoding provides **inherent stochastic noise resilience**: adversarial
  perturbations that shift a classical deterministic weight are distributed across 2^k basis
  states, reducing the per-inference impact.
- Projective measurement collapse introduces irreducible randomness not present in
  deterministic classical networks, reducing the effectiveness of gradient-based adversarial attacks.

**Severity:** MEDIUM for inference-time attacks; HIGH for training-phase manipulation.

**Countermeasures:**
- Syndrome monitoring: anomalous error rate spikes indicate environmental or deliberate attacks
- Differential privacy on Q-STDP updates (clip amplitude updates before normalization)
- Redundant crossbar tiles with majority-vote inference for safety-critical workloads
- Physical access controls on SOT write current sources

---

### 2.3 Hardware Security Primitives Native to QNHS

The QNHS substrate offers several **built-in hardware security advantages** that can be
exploited defensively:

#### 2.3.1 Quantum Dot Physical Unclonable Functions (QD-PUFs)
- Charge noise in 28Si quantum dots exhibits **device-unique stochastic signatures**
  determined by nanoscale dopant distributions and interface trap positions.
- These signatures can serve as Physical Unclonable Functions (PUFs) for device
  authentication without additional hardware.
- Enrollment: measure charge noise spectrum at wafer probe.
- Authentication: challenge-response via qubit frequency shifts under applied gate voltages.

#### 2.3.2 MTJ-Based Quantum Random Number Generation (QRNG)
- Stochastic MTJ switching under sub-threshold current pulses generates **true random bits**
  from thermal fluctuations in the free layer magnetization.
- At 1 K, thermally activated switching rates are well-characterized and can be controlled
  to produce unbiased bit streams at GHz rates.
- Suitable for seeding post-quantum cryptographic key generation.

#### 2.3.3 Quantum Key Distribution (QKD) Integration
- The QCPP spin qubit plane can prepare and measure quantum states for BB84-compatible
  QKD protocols over fiber-optic channels via optical transducers.
- Entanglement distribution between QNHS nodes enables device-authenticated quantum channels.

---

### 2.4 Post-Quantum Cryptography Acceleration

**Context:** NIST finalized the first post-quantum cryptographic standards in August 2024
(FIPS 203: ML-KEM/Kyber; FIPS 204: ML-DSA/Dilithium; FIPS 205: SLH-DSA/SPHINCS+).
Hardware acceleration is critical for embedded and edge deployments.

**QNHS as PQC Accelerator:**
- Lattice-based cryptography (Kyber, Dilithium) relies on polynomial ring arithmetic
  over Z_q that maps efficiently onto matrix-vector products.
- The 256x256 MTJ crossbar implements exactly such products in analog domain (in-memory
  computing), potentially accelerating NTT (Number Theoretic Transform) operations.
- Energy cost estimate: 256x256 PQC matrix multiply at ~11 fJ/MAC = ~720 pJ total,
  vs. ~50 nJ for software implementation on ARM Cortex-M4.

**Relevant Hardware (2025):**
- STMicroelectronics PQC accelerator MCUs (Embedded World 2025)
- IDEMIA Keccak-based PQC hardware accelerator (March 2025)
- FPGA implementations (IACR 2025/1161): ~400 us signing latency on Artix-7

---

### 2.5 Supply Chain and Hardware Trojan Threats

**Threat:** Malicious modifications during fabrication of cryo-CMOS or MTJ layers.

**QNHS-Specific Concern:**
- Hardware Trojans in cryo-CMOS circuits are particularly dangerous because:
  - Standard room-temperature testing does not reveal cryogenic-mode vulnerabilities
  - Trojans can remain dormant at low-frequency test vectors but activate at 1 GHz PLL frequency
  - The MWPM decoder is a high-value target: compromising it corrupts all logical qubits

**Countermeasures:**
- Trusted foundry certification for 3 nm FinFET cryo-CMOS fabrication
- Isotopically enriched 28Si supply chain verification (99.9995% purity testing)
- Post-fabrication characterization at operating temperature (1 K) for all decoder logic
- Logic encryption of the MWPM decoder RTL before tape-out

---

## 3. Threat Matrix Summary

| Threat Vector | Likelihood | Impact | QNHS Mitigation |
|---|---|---|---|
| Timing side-channel (qubit control) | Medium | High | Constant-time scheduling |
| Crosstalk-based algorithm inference | High | High | Physical isolation, shielding |
| Adversarial Q-STDP poisoning | Medium | High | Differential privacy, redundancy |
| MTJ write path manipulation | Low | High | Physical access controls |
| Hardware Trojan (MWPM decoder) | Low | Critical | Trusted foundry, logic encryption |
| Supply chain (28Si purity) | Low | High | Purity certification |
| Quantum circuit leakage via RF | Medium | Medium | EM shielding within cryostat |

---

## 4. References

1. C. Lu et al., "Quantum Leak: Timing Side-Channel Attacks on Cloud-Based Quantum Services,"
   GLSVLSI 2025. DOI: 10.1145/3716368.3735264

2. N. Choudhury et al., "Crosstalk-induced Side Channel Threats in Multi-Tenant NISQ Computers,"
   NDSS 2025. arXiv:2412.10507

3. E. Yocam et al., "Quantum Adversarial Machine Learning and Defense Strategies,"
   arXiv:2412.12373, Dec. 2024.

4. A. Upadhyay et al., "Adversarial Robustness in Quantum Machine Learning: A Scoping Review,"
   Computers, vol. 15, no. 4, p. 233, 2025. DOI: 10.3390/computers15040233

5. NIST, "Post-Quantum Cryptography Standards," FIPS 203/204/205, Aug. 2024.
