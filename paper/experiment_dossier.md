# Experiment Dossier

## 1. Research Questions and Formal Hypotheses

### 1.1 Research Questions (RQs)
- **RQ1**: How does workload irregularity affect the execution time of static, dynamic, and guided scheduling?
- **RQ2**: Under what conditions does dynamic scheduling outperform default static scheduling?
- **RQ3**: Does guided scheduling offer a useful trade-off between load balancing and dispatch overhead?
- **RQ4**: How does chunk size affect performance for each policy?
- **RQ5**: Does spatial clustering of expensive iterations change the relative performance of the scheduling policies, even when the underlying work-cost distribution and CV are the same?
- **RQ6**: How do scheduling conclusions change between the controlled synthetic loop and the Mandelbrot workload?
- **RQ7**: How does thread count affect efficiency, and when do synchronization, scheduling overhead, memory behavior, or available hardware limit scaling?

### 1.2 Formal Hypotheses (H1–H5)
- **Hypothesis 1 (H1)**: *Default static scheduling should be competitive for regular workloads because it distributes work with relatively low coordination cost.*
  - **Verdict**: **Supported**. For regular workloads ($CV = 0$), static scheduling exhibits zero runtime queue coordination overhead, achieving top-tier execution times ($33.75$ ms at 16 threads), whereas dynamic chunk 1 incurs synchronization penalties resulting in an 8.3% regression ($36.55$ ms).
- **Hypothesis 2 (H2)**: *Dynamic scheduling may outperform default static scheduling for irregular workloads when reducing load imbalance more than compensates for added dispatch cost.*
  - **Verdict**: **Strongly Supported**. On randomized high irregularity ($CV = 1.00$), dynamic chunk 64 outperforms static default by $31.2\%$ ($23.42$ ms vs. $34.05$ ms). On clustered high irregularity, dynamic chunk 8 achieves a $67.4\%$ speedup ($22.60$ ms vs. $69.43$ ms) by dynamically routing available threads to heavy iteration blocks.
- **Hypothesis 3 (H3)**: *Guided scheduling may offer a balance between larger early chunks and smaller later chunks, but its performance depends on the workload and chunk configuration.*
  - **Verdict**: **Supported**. Guided chunk 1 achieved the overall lowest runtime on randomized high irregularity ($22.86$ ms, a $32.8\%$ improvement over static default), amortizing initial dispatches with large chunks and resolving stragglers with unit chunks.
- **Hypothesis 4 (H4)**: *The spatial distribution of work can influence scheduling performance independently of the coefficient of variation.*
  - **Verdict**: **Decisively Supported**. Comparing randomized high irregularity ($CV = 1.0035$) against clustered high irregularity ($CV = 1.0035$, identical multiset and identical total work), static default degraded by more than a factor of two ($34.05$ ms vs. $69.43$ ms), whereas dynamic chunk 8 remained virtually unaffected ($24.29$ ms vs. $22.60$ ms).
- **Hypothesis 5 (H5)**: *Small chunks may improve load balancing but can also increase dispatch overhead.*
  - **Verdict**: **Strongly Supported**. Dispatch probe measurements reveal that dynamic chunk 1 incurs $2.75$ ms of dispatch latency at 16 threads, compared to $0.32$ ms for chunk 64 (an 8.6x overhead penalty). When per-iteration work is small, unit chunks severely degrade throughput.

---

## 2. Exact Experiment Matrix

The experimental matrix comprises a full factorial cross-product of:
- **Workloads (6)**:
  1. `regular`: Uniform work cost ($CV = 0.0$)
  2. `random_low`: Gamma-distributed costs ($CV \approx 0.25$)
  3. `random_med`: Gamma-distributed costs ($CV \approx 0.50$)
  4. `random_high`: Gamma-distributed costs ($CV \approx 1.00$)
  5. `clustered_high`: Permutation of `random_high` with top 50% contiguous ($CV \approx 1.00$)
  6. `mandelbrot`: 2D escape-time calculation ($1200 \times 900$, 400 max iterations, $CV \approx 1.65$)
- **Scheduling Configurations (10)**:
  - `static_default` (OpenMP default block division)
  - `static` ($C \in \{1, 8, 64\}$)
  - `dynamic` ($C \in \{1, 8, 64\}$)
  - `guided` ($C \in \{1, 8, 64\}$)
- **Thread Counts (5)**:
  - $P \in \{1, 2, 4, 8, 16\}$
- **Repetitions (7)**:
  - 7 independent measured trials plus 1 initial warm-up run per configuration.

### Total Executed Cells:
- Parallel Workloads: $6 \times 10 \times 5 = 300$ cells $\times 7$ reps = $2,100$ records.
- Serial Baselines: $6 \text{ workloads} \times 7 \text{ reps} = 42$ records.
- Dispatch Probes: $10 \text{ schedules} \times 5 \text{ threads} \times 7 \text{ reps} = 350$ records.
- **Grand Total: 2,492 measurement records**.

---

## 3. Rationale for Workload Selection

1. **Controlled Synthetic Loop**:
   - Isolates CPU arithmetic without memory hierarchy saturation or branch prediction anomalies.
   - Allows exact mathematical calibration of the coefficient of variation ($CV$).
   - Permits perfect conservation of total work budget ($50,000,000$ operations), enabling rigorous apples-to-apples comparisons.
2. **Clustered High vs. Randomized High**:
   - Disentangles the effect of statistical variance ($CV$) from spatial work correlation.
   - Proves that statistical variance alone is insufficient to predict parallel loop load balancing.
3. **Mandelbrot Fractal**:
   - Serves as an authentic scientific benchmark where computational intensity varies continuously across coordinate space.
   - Validates that observations from synthetic benchmarks transfer to real domain problems.

---

## 4. Mapping: Raw Columns to Processed Metrics and Figures

| Raw CSV Column | Processed Metric (`summary.csv`) | Purpose & Role | Plotted in Figures |
| :--- | :--- | :--- | :--- |
| `elapsed_ms` | `median_ms`, `mean_ms`, `std_ms`, `time_ci95_*` | Core runtime point estimate and bootstrap variability | Fig 1, Fig 5, Fig 6, Fig 7, Fig 9 |
| `elapsed_ms` (serial vs par) | `speedup`, `speedup_ci95_*` | $S_p = \tilde{T}_{\text{serial}} / \tilde{T}_{\text{parallel}}$ | Fig 2, Fig 9 |
| `speedup`, `requested_threads` | `efficiency`, `efficiency_ci95_*` | $E_p = S_p / P$ | Fig 4 |
| `elapsed_ms` (probe) | `probe_overhead_ms` (`overhead.csv`) | Coordination latency proxy | Fig 3, Fig 8 |
| `probe_overhead_ms`, `median_ms` | `probe_overhead_pct` | Overhead percentage of execution time | Fig 3 |
| `median_ms` (vs static default) | `relative_improvement_pct` | Relative speedup vs. default static | Fig 10 |
| `actual_cv` | `actual_cv` | Empirically measured cost dispersion | Fig 3, Fig 5, Fig 10 |
| `chunk_size` | `chunk_size` | Chunk granularity evaluation | Fig 6, Fig 8 |
| `requested_threads` | `requested_threads` | Parallel scaling factor | Fig 1, Fig 2, Fig 4, Fig 9, Fig 10 |

---

## 5. Implementation Decisions and Technical Rationale

1. **Separate Serial Implementation**:
   - The serial baseline was built as a standalone function compiled without OpenMP pragmas (`run_synthetic_serial` and `run_mandelbrot_serial`), rather than calling a 1-thread OpenMP parallel region. This eliminates OpenMP runtime library entry/exit and barrier overhead from the serial reference.
2. **Explicit Static Default vs. Runtime Scheduling**:
   - In OpenMP, `schedule(static)` without a chunk size divides $N$ into $P$ contiguous chunks of size approximately $\lceil N/P \rceil$. Chunked static `schedule(static, C)` distributes chunks in a cyclic round-robin pattern. We preserved this distinction explicitly in both the C++ source and CSV records (`chunk_size="default"` vs `"1"`, `"8"`, `"64"`).
3. **Affinity and Dynamic Thread Disabling**:
   - Set `OMP_DYNAMIC=FALSE` and explicitly pinned threads using `OMP_PLACES=cores` and `OMP_PROC_BIND=close`. This prevents operating system thread migration across physical cores during timing loops.
4. **Run-Order Randomization**:
   - Executing configurations in fixed order can induce systematic drift due to thermal throttling or frequency boost degradation. Shuffling all 300 configs within each repetition guaranteed unbiased sampling.
5. **Deterministic Checksums**:
   - A 64-bit FNV-1a hash was computed across the output array after each timed region. All runs of a workload yielded the exact same hash across serial and parallel executions, verifying 100% computational correctness.

---

## 6. Protocol Deviations and Calibrations
- **Calibration Adjustment**: Pilot benchmarks showed that setting $N = 100,000$ and $W_{\text{base}} = 500$ operations yielded single-threaded runtimes of $\approx 275$ ms and 16-threaded runtimes of $\approx 23-35$ ms. This provided ideal experimental fidelity without introducing timer resolution error or thermal throttling.
- No other protocol deviations occurred. All experiments executed to completion on the physical host hardware.
