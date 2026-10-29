# CS2: Advanced Scheduling and Load Balancing
## S01: Static vs. Dynamic OpenMP Scheduling Study

[![Build & Test](https://img.shields.io/badge/Build%20%26%20Test-Passed-brightgreen.svg)]()
[![OpenMP](https://img.shields.io/badge/OpenMP-4.5%20%2F%20libgomp-blue.svg)]()
[![C++17](https://img.shields.io/badge/C%2B%2B-17-orange.svg)]()
[![Python](https://img.shields.io/badge/Python-3.12-yellow.svg)]()

---

## 1. Project Objective and Research Question

This repository contains the complete experimental framework, source code, data analysis pipelines, and publication-ready artifacts for an advanced empirical study on OpenMP loop self-scheduling.

### Main Research Question
> **Under what workload conditions does OpenMP dynamic scheduling outperform static scheduling, and how do guided scheduling, chunk size, thread count, workload irregularity, and scheduling overhead affect performance?**

### Key Hypotheses Investigated
1. **H1 (Static on Regular)**: Default static scheduling is competitive for regular workloads because it eliminates runtime dispatch coordination.
2. **H2 (Dynamic on Irregular)**: Dynamic scheduling outperforms static scheduling when reducing load imbalance outweighs runtime dispatch contention.
3. **H3 (Guided Scheduling)**: Guided scheduling balances large initial chunks with small tail chunks, but its efficacy depends on workload geometry.
4. **H4 (Spatial Clustering)**: Spatial clustering of expensive iterations degrades static scheduling independently of the workload's coefficient of variation ($CV$).
5. **H5 (Chunk Contention)**: Unit chunks ($C=1$) provide fine-grained load balancing at the cost of high dispatch contention on atomic work queues.

---

## 2. Directory Structure

```text
cs2-scheduling-study/
├── CMakeLists.txt                 # C++17 & OpenMP CMake build configuration
├── README.md                      # Comprehensive user & reproduction guide
├── src/
│   ├── benchmark_support.hpp      # Workload generators, dispatchers, fractals, probes
│   └── benchmark.cpp              # CLI benchmark executable with CSV & profiling modes
├── tests/
│   └── correctness_tests.cpp      # Correctness verification suite (CTest integration)
├── scripts/
│   ├── run_experiments.py         # Automated matrix runner with order randomization
│   ├── analyze_results.py         # Statistical analysis (bootstrap CIs) and 10 figures
│   └── validate_results.py        # Quality assurance & checksum consistency validator
├── results/
│   ├── raw/
│   │   ├── raw_runs.csv           # 2,492 raw execution records with checksums
│   │   └── environment.json       # Detected CPU, compiler, OS, and affinity metadata
│   └── processed/
│       ├── summary.csv            # Statistical summaries (medians, means, 95% CIs)
│       ├── speedup.csv            # Parallel speedup point estimates & bootstrap CIs
│       ├── efficiency.csv         # Parallel efficiency metrics
│       ├── overhead.csv           # Low-work dispatch probe measurements
│       ├── workload_statistics.csv# Mathematical profiles of tested workloads
│       └── analysis_metadata.json # Analysis execution metadata
├── figures/
│   ├── png/                       # 10 publication-quality figures (300 DPI PNG)
│   └── pdf/                       # 10 vector format publication figures (PDF)
├── paper/
│   ├── methodology.md             # Experimental design, formulas, and calibration
│   ├── experiment_dossier.md       # Matrix specification, hypotheses, and mappings
│   ├── results_summary.md         # Key findings quoting exact empirical measurements
│   ├── paper_outline.md           # 11-section publication manuscript structure
│   ├── threats_to_validity.md     # Threats to validity (internal, external, construct)
│   └── references.bib             # Curated scholarly bibliography
└── logs/                          # Stdout/stderr logs from tests and experiment runs
```

---

## 3. System Requirements and Dependencies

### System Toolchain
- **C++ Compiler**: GCC 13.3+ or Clang 16+ supporting C++17 and OpenMP (`-fopenmp`).
- **Build System**: CMake 3.16+ (`cmake`).
- **Runtime Library**: GNU `libgomp` or LLVM `libomp`.
- **Operating System**: Linux x86-64 (tested on Ubuntu 24.04 LTS / WSL2, kernel 6.6.87).

### Python Scientific Stack
- Python 3.10+
- `numpy >= 1.24`
- `pandas >= 2.0`
- `matplotlib >= 3.7`
- `scipy >= 1.10`

---

## 4. Build and Test Instructions

### Step 1: Configure and Build the Project
Configure with CMake in optimized `Release` mode:
```bash
cd cs2-scheduling-study
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
```

### Step 2: Run Correctness Tests
Execute the automated test suite via CTest:
```bash
ctest --test-dir build --output-on-failure
```
Alternatively, run the test binary directly:
```bash
./build/correctness_tests
```
The test suite validates:
1. Workload generation determinism for fixed seeds.
2. Regular workload zero-variance ($CV = 0.0$).
3. Gamma-distributed irregularity scaling ($CV \approx 0.25, 0.50, 1.00$).
4. Exact multiset, histogram, and total-work conservation between randomized and clustered profiles.
5. 100% checksum agreement between serial baselines and all 10 parallel scheduling policies.
6. Mandelbrot parallel checksum equivalence.
7. Dispatch probe execution agreement.
8. Thread count observation consistency.
9. Parameter validation and error handling.

---

## 5. Running the Experiments

### Quick Pilot / Smoke Test Mode
To verify the entire execution and data logging pipeline in under 20 seconds:
```bash
python3 scripts/run_experiments.py --quick
```

### Full Benchmark Execution
To execute the complete factorial experiment matrix across all 6 workloads, 10 schedules, and 5 thread counts with 7 measured repetitions:
```bash
python3 scripts/run_experiments.py --repeats 7 --max-threads 16
```

### Custom Benchmark Arguments
`scripts/run_experiments.py` supports configurable CLI arguments:
- `--repeats <N>`: Number of measured repetitions per cell (default: `7`).
- `--warmup <N>`: Number of untimed warmup iterations (default: `1`).
- `--max-threads <N>`: Maximum thread cap (default: `16`).
- `--threads <list>`: Comma-separated list of threads (e.g., `--threads 1,2,4,8,16`).
- `--iterations <N>`: Synthetic loop iteration count (default: `100000`).
- `--base-work <W>`: Base work units per iteration (default: `500`).
- `--seed <S>`: Random seed for workload and order randomization (default: `42`).
- `--mandel-width <W>`: Mandelbrot pixel width (default: `1200`).
- `--mandel-height <H>`: Mandelbrot pixel height (default: `900`).
- `--mandel-max-iter <I>`: Maximum escape iteration threshold (default: `400`).

---

## 6. Validating Experimental Integrity

Verify the integrity, completeness, and deterministic checksum agreement of the saved raw data:
```bash
python3 scripts/validate_results.py results/raw/raw_runs.csv --expected-repeats 7
```

---

## 7. Statistical Analysis and Figure Generation

To process raw measurements, compute non-parametric bootstrap confidence intervals, and regenerate all 10 publication figures without re-running benchmarks:
```bash
python3 scripts/analyze_results.py
```

### Generated Figures
All figures are saved simultaneously as high-resolution PNG (`figures/png/*.png`, 300 DPI) and vector PDF (`figures/pdf/*.pdf`):
- **Figure 1**: Execution Time vs. Thread Count (small multiples across workloads).
- **Figure 2**: Parallel Speedup vs. Thread Count (with ideal linear reference).
- **Figure 3**: Low-Work Dispatch Probe Overhead Proxy vs. Irregularity ($CV$).
- **Figure 4**: Parallel Efficiency (%) vs. Thread Count.
- **Figure 5**: Execution Time vs. Actual Workload $CV$ (at 8 and 16 threads).
- **Figure 6**: Chunk-Size Sensitivity for Static, Dynamic, and Guided Scheduling.
- **Figure 7**: Spatial Clustering Comparison: Randomized vs. Clustered High Irregularity.
- **Figure 8**: Low-Work Dispatch Overhead vs. Chunk Size.
- **Figure 9**: Mandelbrot Domain Benchmark Execution Time and Speedup.
- **Figure 10**: Relative Performance Heatmap (% Speedup over Static Default).

---

## 8. Metric Definitions

- **Wall-Clock Execution Time ($T$)**: Elapsed wall-clock time in milliseconds measured with `omp_get_wtime()`. Includes parallel region fork/join, loop scheduling dispatch, and barrier synchronization.
- **Speedup ($S_p$)**: Ratio of genuine serial runtime to parallel runtime:
  $$S_p(w, c, P) = \frac{\tilde{T}_{\text{serial}}(w)}{\tilde{T}_{\text{parallel}}(w, c, P)}$$
- **Parallel Efficiency ($E_p$)**: Speedup normalized by thread concurrency:
  $$E_p = \frac{S_p}{P}$$
- **Dispatch Overhead Proxy ($T_{\text{probe}}$)**: Elapsed runtime (ms) of a minimal-work loop under identical loop bounds, schedule, and thread configurations.
- **Relative Improvement ($\Delta T_{\text{rel}}$)**: Percentage execution time improvement over default static scheduling:
  $$\Delta T_{\text{rel}} = \frac{\tilde{T}_{\text{static\_default}} - \tilde{T}_{\text{policy}}}{\tilde{T}_{\text{static\_default}}} \times 100\%$$

---

## 9. Machine-Specific Information and Limitations

- **Host Processor**: AMD Ryzen 7 6800H with Radeon Graphics (8 physical cores, 16 SMT threads).
- **Cache Topology**: 16 MiB shared L3 cache, single NUMA node.
- **Operating Environment**: Linux 6.6.87.1-microsoft-standard-WSL2 on Ubuntu 24.04 LTS.
- **Affinity Settings**: Threads are bound to cores via `OMP_DYNAMIC=FALSE`, `OMP_PLACES=cores`, and `OMP_PROC_BIND=close`.
- **Note on Generalizability**: Single NUMA node mobile/desktop APU. Multi-socket NUMA systems and heterogeneous architectures (e.g., Intel big.LITTLE) will introduce additional NUMA queue latency not observed in this single-node evaluation.
# Parallel-Computing-scheduling-study
