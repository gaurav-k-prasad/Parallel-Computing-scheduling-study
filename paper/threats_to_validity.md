# Threats to Validity

This document outlines the methodological and experimental limitations of this study, categorized into internal, external, construct, and conclusion validity.

---

## 1. Internal Validity

### 1.1 CPU Dynamic Frequency Scaling and Thermal Throttling
Modern x86-64 microprocessors, including the AMD Ryzen 7 6800H, feature sophisticated dynamic voltage and frequency scaling (DVFS) algorithms (such as AMD Precision Boost and thermal throttling governors).
- **Threat**: When transitioning from single-threaded baselines to 16-threaded execution, all-core boost clocks are typically lower than single-core peak boost clocks (e.g., 3.2–3.8 GHz all-core vs. up to 4.7 GHz single-core). This dynamic frequency adjustment can cause parallel execution times to appear artificially prolonged, reducing observed speedups ($S_p$).
- **Mitigations Applied**:
  - We implemented **run-order randomization** within each repetition: the 300 parallel configurations were shuffled pseudorandomly, preventing sequential heating from biasing specific policies.
  - A dedicated untimed **warmup run** was executed before measurement trials to ensure thread pools and frequency states were pre-warmed.
  - Exactly 7 independent trials were executed, and median statistics were utilized to minimize sensitivity to brief thermal spikes.

### 1.2 Operating System Background Processes and Virtualization Noise
The experiments were executed within WSL2 (Windows Subsystem for Linux, Linux kernel 6.6.87.1) running atop Windows 11.
- **Threat**: Hypervisor scheduling slices, host OS background processes, and virtualization interrupts can introduce non-deterministic execution jitter.
- **Mitigations Applied**:
  - OpenMP worker threads were pinned to processor cores using explicit affinity environment variables: `OMP_DYNAMIC=FALSE`, `OMP_PLACES=cores`, and `OMP_PROC_BIND=close`.
  - Non-parametric bootstrap confidence intervals ($B = 2000$) were computed to quantify experimental variance explicitly.

### 1.3 Execution Order and Memory Boundary Effects
- **Threat**: Running identical schedules consecutively could benefit from residual cache warming, whereas changing schedules might induce cache eviction overhead.
- **Mitigations Applied**: Randomizing the execution sequence eliminated systematic correlation between test order and measured runtime.

---

## 2. External Validity (Generalizability)

### 2.1 Single-Architecture and Single-Host Evaluation
- **Threat**: The evaluation was performed on a single mobile/workstation CPU architecture: AMD Ryzen 7 6800H (Zen 3+, 8 physical cores, 16 SMT threads, single NUMA node with 16 MiB shared L3 cache).
- **Implications**: The findings may not directly extrapolate to:
  - Multi-socket server architectures with Non-Uniform Memory Access (NUMA) topologies, where dynamic queue access across NUMA sockets incurs heavy interconnect penalties.
  - Intel hybrid architectures featuring heterogeneous performance (P) and efficient (E) cores with asymmetric clock frequencies.
  - Massively parallel processors (e.g., 64- or 128-core AMD EPYC systems) where atomic queue contention in `dynamic` scheduling scales with $P$.

### 2.2 Compiler and OpenMP Runtime Implementation Differences
- **Threat**: The study was compiled with GCC 13.3.0 and executed against GNU `libgomp`.
- **Implications**: OpenMP loop scheduling algorithms are runtime-dependent. LLVM's `libomp` and Intel's `libiomp5` utilize different internal synchronization primitives, work-stealing heuristics, and chunk allocation strategies. In particular, GNU `libgomp` uses centralized spinlocks for dynamic work queues, whereas LLVM utilizes different internal lock-free or queue optimizations. Findings regarding exact dispatch latency values should be interpreted as specific to `libgomp`.

### 2.3 Selected Problem Sizes and Chunk Configurations
- **Threat**: We evaluated chunk sizes $C \in \{1, 8, 64\}$ across an iteration space of $N = 100,000$ (synthetic) and $N = 1,080,000$ (Mandelbrot).
- **Implications**: Applications with millions of iterations or very large chunk sizes ($C \ge 1024$) will exhibit different overhead ratios. Our selection represents fine-to-medium grain worksharing commonly encountered in scientific simulations.

---

## 3. Construct Validity

### 3.1 Limitations of the Low-Work Dispatch Probe as an Overhead Proxy
- **Threat**: The dispatch probe loop executes minimal arithmetic per iteration to isolate runtime scheduling, parallel region entry/exit, and barrier latency. It is not an exact direct measurement of internal OpenMP scheduler instruction cycles.
- **Implications**:
  - The probe represents a *lower bound* proxy for dispatch overhead under ideal ALU-only conditions.
  - In a real application, threads contending for dynamic work queues also contend for shared cache lines, memory controllers, and execution units.
  - Therefore, dispatch probe times **must not** be subtracted naively from real workload runtimes to calculate "useful computation." We explicitly treat the probe as a comparative proxy.

### 3.2 Synthetic Kernel vs. Real-World Application Realism
- **Threat**: The synthetic benchmark utilizes deterministic integer hashing with loop-carried dependencies to prevent compiler elimination.
- **Implications**: While ideal for isolating CPU-bound scheduling behavior with zero memory allocation interference, it does not capture complex memory access patterns, cache misses, branch mispredictions, or vectorization characteristics present in full-scale scientific codes.
- **Mitigation**: We included the Mandelbrot fractal computation as a secondary validation benchmark, demonstrating that the synthetic conclusions transfer to an authentic computational domain.

### 3.3 Limitations of Coefficient of Variation ($CV$)
- **Threat**: Relying solely on the coefficient of variation ($CV = \sigma / \mu$) to characterize workload irregularity is fundamentally incomplete.
- **Evidence from Study**: The Randomized High and Clustered High workloads possessed the exact same $CV = 1.0035$ and identical total work ($50,000,000$ operations), yet static default scheduling performed more than $2\text{x}$ slower on the clustered profile ($69.43$ ms vs. $34.05$ ms).
- **Conclusion**: Spatial autocorrelation of work across the iteration space is equally or more important than statistical dispersion when predicting parallel load imbalance.

---

## 4. Conclusion Validity

### 4.1 Sample Size and Statistical Significance
- **Threat**: Experimental conclusions drawn from too few trials or biased by outliers can lead to erroneous inferences.
- **Mitigation**:
  - We collected 7 independent repetitions for every one of the 356 experimental cells, yielding 2,492 measurement records.
  - We employed non-parametric bootstrap resampling ($B = 2000$) to construct empirical 95% confidence intervals for medians and speedup ratios.
  - We refrain from making universal optimality claims, reporting policy advantages strictly within the tested parameter boundaries.
