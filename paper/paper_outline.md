# Research Paper Outline: Static vs. Dynamic OpenMP Loop Scheduling

## Title
**Dissecting Loop Self-Scheduling in OpenMP: How Workload Irregularity, Spatial Clustering, and Dispatch Contention Govern Parallel Efficiency**

---

## 1. Abstract
- Context: OpenMP loop scheduling remains a cornerstone of shared-memory parallel programming.
- Problem: Developers often rely on default static scheduling or select dynamic scheduling arbitrarily without understanding how workload coefficient of variation ($CV$), spatial concentration of work, and chunk-size coordination costs interact.
- Methodology: Empirical evaluation on an AMD Ryzen 7 6800H (8 physical cores, 16 SMT threads) using GCC 13.3.0 and libgomp. Controlled synthetic loops with mathematically calibrated $CV \in [0.0, 1.0]$ and strictly conserved total work budgets ($50 \times 10^6$ ops), paired with a Mandelbrot fractal domain benchmark and a low-work dispatch probe.
- Key Results:
  - Statistical variance ($CV$) alone is insufficient to predict load imbalance: spatial clustering of high-cost iterations degrades default static scheduling by $104\%$ ($69.43$ ms vs. $34.05$ ms), while dynamic scheduling with chunk size 8 maintains superior throughput ($22.60$ ms, a $67.4\%$ speedup over static default).
  - For regular loops, dynamic scheduling with unit chunks regresses by $8.3\%$ due to atomic queue lock contention ($2.75$ ms probe latency).
  - Across irregular and domain workloads, medium chunk sizes ($C = 8$) provide the optimal balance between queue amortization and load balance.
- Significance: Provides concrete guidelines for OpenMP schedule selection based on loop structure and hardware topology.

---

## 2. Introduction and Motivation
- The ubiquity of multi-core shared-memory architectures and OpenMP loop worksharing (`#pragma omp for`).
- The trade-off between static scheduling (low dispatch overhead, vulnerability to load imbalance) and dynamic/guided self-scheduling (runtime adaptability, synchronization penalties).
- Gap in literature: Many studies examine either purely regular benchmarks or unstructured irregular applications, without systematically decoupling statistical variance ($CV$) from spatial work correlation.
- Summary of contributions:
  1. A mathematically rigorous controlled synthetic loop maintaining invariant work budgets while varying $CV$ and spatial clustering.
  2. A low-work dispatch probe quantifying empirical runtime coordination overhead.
  3. A 2,492-measurement empirical study across 10 schedule variants, 5 thread counts, and 6 workload profiles.

---

## 3. Research Questions and Hypotheses
- Formal statement of RQ1 through RQ7.
- Presentation of Hypotheses H1 through H5.
- Clear criteria for hypothesis validation based on median runtimes, speedup ratios, and bootstrap confidence intervals.

---

## 4. Background and Related Work
- Theoretical foundations of loop self-scheduling:
  - Static block and block-cyclic scheduling.
  - Guided self-scheduling (Polychronopoulos and Kuck, 1987).
  - Factoring algorithms (Hummel et al., 1992).
  - Microbenchmark suites and OpenMP runtime overhead measurement (Bull, 1999; Bull & O'Neill, 2001).
  - OpenMP 5.2 worksharing specification and libgomp implementation details.
- Clear demarcation between prior literature and this empirical study.

---

## 5. Experimental Methodology
- Experimental design: Independent and dependent variables.
- Parametric workload generation: Gamma distribution shaping, scaling, remainder allocation, and spatial permutation.
- Mandelbrot escape-time benchmark parameters.
- Low-work dispatch probe formulation and interpretation limits.
- System hardware architecture, Linux kernel, compiler optimization flags, and OpenMP affinity bindings (`OMP_PLACES=cores`, `OMP_PROC_BIND=close`).
- Execution protocol: Warm-up iterations, 7 measured repeats, and run-order randomization.
- Statistical framework: Point estimates (medians), dispersion (std dev), non-parametric bootstrap confidence intervals ($B=2000$).

---

## 6. Implementation
- C++17 architectural structure (`benchmark_support.hpp`, `benchmark.cpp`).
- Deterministic 64-bit integer mixing kernel and loop-carried dependencies.
- OpenMP runtime scheduling dispatchers and verification via `omp_get_schedule()`.
- Standalone serial baselines compiled without OpenMP pragmas.
- Automated testing via CTest verifying checksum agreement and conservation invariants.

---

## 7. Results
- **7.1 Workload Irregularity Impact (RQ1)**:
  - Transition from regular ($CV=0$) to high irregularity ($CV=1.0$).
  - Analysis of runtime scaling across thread counts (Figure 1, Figure 5).
- **7.2 Dynamic vs. Static Default Crossover (RQ2)**:
  - Identification of conditions where dynamic scheduling yields superior performance.
  - Discussion of the $8.3\%$ regression on regular workloads vs. $31.2\%$ improvement on random high irregularity (Figure 10).
- **7.3 Guided Scheduling Characteristics (RQ3)**:
  - Analysis of guided self-scheduling achieving $12.10\text{x}$ speedup on randomized high irregularity while underperforming on Mandelbrot.
- **7.4 Chunk Size Sensitivity and Dispatch Overhead (RQ4, H5)**:
  - Empirical overhead of unit chunks ($C=1$) vs. chunked variants ($C=8, 64$).
  - Dispatch probe results: $2.75$ ms for dynamic chunk 1 vs. $0.32$ ms for chunk 64 (Figure 3, Figure 8).
- **7.5 Spatial Clustering vs. Statistical Variance (RQ5, H4)**:
  - Deep-dive into Randomized High vs. Clustered High workloads.
  - Proof that spatial distribution induces a 2x slowdown in static scheduling despite identical CV and equal total work (Figure 7).
- **7.6 Validation on Mandelbrot Domain Benchmark (RQ6)**:
  - Evaluation of 2D fractal computation; top performance of `dynamic_c8` ($50.13$ ms, $S_p = 9.55\text{x}$) (Figure 9).
- **7.7 Thread Scaling, SMT, and Parallel Efficiency (RQ7)**:
  - Scaling across 1, 2, 4, 8 physical cores and 16 SMT threads (Figure 2, Figure 4).

---

## 8. Discussion
- Synthesis of findings and architectural implications.
- Memory subsystem interactions: False sharing avoidance via chunking.
- The role of hardware thread interleaving (SMT) when pipelines are stalled by irregular branching or memory operations.
- Practical developer recommendations: A decision framework for selecting OpenMP schedules based on iteration variance, spatial correlation, and loop iteration count.

---

## 9. Threats to Validity
- Comprehensive treatment of internal, external, construct, and conclusion validity (cross-referencing `threats_to_validity.md`).

---

## 10. Conclusion
- Summary of core answers to RQ1–RQ7.
- Final takeaways on OpenMP loop scheduling best practices.
- Directions for future research (e.g., dynamic work-stealing tasks, NUMA architectures, GPU offloading).

---

## 11. References
- Full bibliographic citations corresponding to `references.bib`.
