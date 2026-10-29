# Experimental Methodology

## 1. Experimental Overview and Objectives
This research study investigates the runtime performance, load balancing efficacy, and dispatch coordination overhead of OpenMP loop scheduling policies. The primary research question is:
> *Under what workload conditions does OpenMP dynamic scheduling outperform static scheduling, and how do guided scheduling, chunk size, thread count, workload irregularity, and scheduling overhead affect performance?*

To answer this question rigorously, we establish an experimental framework incorporating:
1. A **controlled synthetic loop benchmark** with deterministic, parametrically controlled work costs per iteration.
2. A **secondary domain benchmark (Mandelbrot fractal computation)** featuring natural, spatially non-uniform workload irregularity.
3. A **low-work dispatch probe loop** designed to isolate OpenMP parallel runtime scheduling and synchronization overhead.

---

## 2. Experimental Design and Variables

### 2.1 Independent Variables
The experiment controls six independent variables:
1. **Scheduling Policy**:
   - `static` (default block division)
   - `static` with explicit chunk size
   - `dynamic` with explicit chunk size
   - `guided` with explicit chunk size
2. **Chunk Size ($C$)**:
   - $C \in \{1, 8, 64\}$ iterations, alongside the unchunked `static (default)` baseline.
   - Total of 10 distinct scheduling configurations:
     - `static_default`
     - `static_c1`, `static_c8`, `static_c64`
     - `dynamic_c1`, `dynamic_c8`, `dynamic_c64`
     - `guided_c1`, `guided_c8`, `guided_c64`
3. **Thread Count ($P$)**:
   - $P \in \{1, 2, 4, 8, 16\}$ threads.
   - Specifically chosen to span single-core execution ($P=1$), sub-socket scaling ($P=2, 4$), the physical core boundary ($P=8$, AMD Ryzen 7 6800H physical cores), and the full logical simultaneous multithreading (SMT) capacity ($P=16$).
4. **Workload Irregularity (Coefficient of Variation, $CV$)**:
   - Regular: Target $CV = 0.0$
   - Randomized Low: Target $CV = 0.25$
   - Randomized Moderate: Target $CV = 0.50$
   - Randomized High: Target $CV = 1.00$
5. **Spatial Workload Arrangement**:
   - *Randomized High Irregularity*: Iteration costs distributed uniformly at random across loop indices.
   - *Clustered High Irregularity*: Identical multiset/histogram of iteration costs, but with the top 50% most computationally expensive iterations contiguous in the central half $[N/4, 3N/4)$ of the loop index space.
6. **Workload Class**:
   - Controlled synthetic kernel (fixed total arithmetic work budget).
   - Mandelbrot escape-time fractal calculation ($1200 \times 900$ complex plane grid, maximum 400 iterations).

### 2.2 Dependent Variables
1. **Wall-clock Execution Time ($T$)**: Elapsed milliseconds measured via `omp_get_wtime()`.
2. **Parallel Speedup ($S_p$)**: Ratio of genuine serial execution time to parallel execution time.
3. **Parallel Efficiency ($E_p$)**: Speedup normalized by thread count ($E_p = S_p / P$).
4. **Low-Work Dispatch Overhead Proxy ($T_{\text{probe}}$)**: Elapsed runtime of a minimal work loop under identical loop bounds, schedule, chunk, and thread configurations.
5. **Dispatch Overhead Ratio ($R_{\text{probe}}$)**: Percentage of workload execution time consumed by the dispatch probe ($T_{\text{probe}} / T_{\text{workload}} \times 100\%$).
6. **Relative Performance Gain/Loss ($\Delta T_{\text{rel}}$)**: Percentage improvement in execution time relative to default static scheduling.

---

## 3. Workload Generation and Controlled Irregularity

### 3.1 Synthetic Workload Construction
To eliminate interference between timing and allocation or pseudo-random generation, iteration work costs $W[i]$ ($i = 0, \dots, N-1$) are computed ahead of time during an untimed initialization phase.

Let $N = 100,000$ iterations and base work $W_{\text{base}} = 500$ operations. The total computational work budget is strictly fixed across all synthetic profiles:
$$B = \sum_{i=0}^{N-1} W[i] = N \times W_{\text{base}} = 50,000,000 \text{ work units}$$

1. **Regular Workload**:
   $$W[i] = W_{\text{base}} = 500, \quad \forall i \in [0, N-1]$$
   Produces an exact theoretical and empirical $CV = 0.0$.

2. **Randomized Irregularity (Gamma Distribution)**:
   A continuous Gamma distribution $\Gamma(k, \theta)$ has mean $\mu = k\theta$, variance $\sigma^2 = k\theta^2$, and coefficient of variation $CV = \sigma/\mu = 1/\sqrt{k}$. Setting shape $k = 1/CV^2$ and $\theta = 1.0$:
   - For target $CV = 0.25$: $k = 16.0$
   - For target $CV = 0.50$: $k = 4.0$
   - For target $CV = 1.00$: $k = 1.0$ (standard exponential distribution)

   Raw continuous variates $X_i \sim \Gamma(k, 1.0)$ are generated using `std::mt19937_64` seeded with $S = 42$. Variates are scaled to the budget $B$:
   $$Y_i = \frac{X_i}{\sum_{j=0}^{N-1} X_j} \times B$$
   To ensure every iteration performs positive integer work without altering $B$, integer costs are assigned via $W_i = \max(1, \lfloor Y_i \rfloor)$. The integer deficit or surplus $D = B - \sum_{i} W_i$ is distributed deterministically by sorting fractional remainders $(Y_i - \lfloor Y_i \rfloor)$, with tie-breaking on index $i$.

   This mathematical procedure ensures that:
   - Every iteration $W_i \ge 1$.
   - $\sum_{i=0}^{N-1} W_i = 50,000,000$ exactly across all profiles.
   - The generation is 100% deterministic and reproducible.

3. **Clustered High Irregularity**:
   The generated integer vector from *Randomized High* is sorted in ascending order. The lowest 50% of iterations are distributed to the outer regions $[0, N/4)$ and $[3N/4, N)$, while the highest 50% are placed contiguously in the central region $[N/4, 3N/4)$.
   Because this is a pure permutation of the randomized high-irregularity array, the multiset, histogram, mean, variance, standard deviation, and actual $CV$ are **strictly identical** to the randomized case. Any performance difference between randomized and clustered profiles is exclusively attributable to the spatial arrangement of work across the iteration space.

### 3.2 Synthetic Kernel Implementation
Within iteration $i$, the kernel performs an inner loop of $W[i]$ iterations of 64-bit integer mixing:
```cpp
uint64_t state = static_cast<uint64_t>(i) ^ 0x9e3779b97f4a7c15ULL;
for (uint32_t step = 0; step < W[i]; ++step) {
    state ^= (state >> 30);
    state *= 0xbf58476d1ce4e5b9ULL;
    state ^= (state >> 27);
    state *= 0x94d049bb133111ebULL;
    state ^= (state >> 31);
    state += step;
}
out[i] = state;
```
This kernel exhibits loop-carried dependency, preventing the compiler from applying closed-form algebraic simplification, while remaining purely CPU-bound and cache-friendly (writing to independent elements of a preallocated output buffer).

### 3.3 Mandelbrot Domain Benchmark
The Mandelbrot calculation evaluates the escape iteration count for complex coordinates $c_0 = x_0 + i y_0$ sampled uniformly on a $1200 \times 900$ grid over $x \in [-2.0, 0.5]$ and $y \in [-1.25, 1.25]$ with maximum iteration limit 400.
The loop is flattened to $N = 1,080,000$ iterations, mapping directly onto OpenMP 1D parallel worksharing. Per-pixel escape counts provide a natural proxy for computational cost without synthetic artificiality.

---

## 4. Scheduling Overhead Proxy Methodology
OpenMP runtimes do not expose portable, non-invasive internal hardware event counters for chunk queue synchronization. To measure scheduling and dispatch costs empirically, we implement a **low-work dispatch probe loop**.
- The probe iterates over the exact same iteration count $N = 100,000$ as the synthetic benchmark.
- It executes under the exact same scheduling policy, chunk size $C$, and thread count $P$.
- Each iteration performs minimal arithmetic (`out[i] = (i * 3141592653589793238ULL) ^ 0x5a5a5a5a5a5a5a5aULL`) to prevent compiler dead-code elimination while minimizing ALU execution time.
- The probe timing captures `#pragma omp parallel` entry/exit, thread fork/join, thread synchronization, atomic chunk queue locks, and barrier latency.

> [!NOTE]
> The dispatch probe is a *proxy* representing the lower bound on loop coordination and dispatch latency. It should not be subtracted naively from workload execution time to infer "pure computation," because memory bus contention, cache interference, and thread interleaving interact non-linearly under heavy compute loads.

---

## 5. Hardware and Software Environment

| Component | Specification |
| :--- | :--- |
| **Processor** | AMD Ryzen 7 6800H with Radeon Graphics |
| **Microarchitecture** | Zen 3+ (Rembrandt, 6nm, Family 25, Model 68) |
| **Cores / Threads** | 8 physical cores, 16 logical processors (2 threads/core SMT) |
| **Base / Max Clock** | 3.2 GHz base, up to 4.7 GHz boost |
| **Caches** | L1d: 8x 32 KiB, L1i: 8x 32 KiB, L2: 8x 512 KiB, L3: 16 MiB shared |
| **System Memory** | 7.4 GiB RAM allocated to Linux environment (WSL2) |
| **Operating System** | Linux 6.6.87.1-microsoft-standard-WSL2 (Ubuntu 24.04 LTS x86_64) |
| **Compiler** | GNU C++ Compiler (`g++` 13.3.0) |
| **Build Flags** | `-O3 -Wall -Wextra -Wpedantic -DNDEBUG` (CMake Release) |
| **OpenMP Runtime** | GNU libgomp (OpenMP 4.5 specification date 201511) |
| **OpenMP Affinity** | `OMP_DYNAMIC=FALSE`, `OMP_PLACES=cores`, `OMP_PROC_BIND=close` |
| **Python Stack** | Python 3.12.7, NumPy 1.26.4, pandas 2.2.2, Matplotlib 3.9.2, SciPy 1.13.1 |

---

## 6. Execution Protocol and Reproducibility

### 6.1 Calibration and Workload Sizing
During the calibration phase, problem parameters ($N = 100,000$, $W_{\text{base}} = 500$; Mandelbrot $1200 \times 900$, 400 max iterations) were verified on single-threaded baselines:
- Synthetic serial baseline takes $\approx 272-277$ ms.
- Mandelbrot serial baseline takes $\approx 479$ ms.
- Highly parallel configurations take $\approx 20-50$ ms.
This range guarantees that execution times are three to four orders of magnitude greater than system timer resolution ($\approx 10$ ns for `omp_get_wtime()`), preventing quantization noise while avoiding thermal degradation over extended benchmark runs.

### 6.2 Repeated Trials and Run-Order Randomization
1. **Warmup Runs**: Every configuration executes one untimed warmup invocation before measurement to prime instruction caches, initialize OpenMP thread worker pools, and stabilize CPU frequency governors.
2. **Repetition Count**: Exactly 7 independent measured repetitions are collected for every experimental cell.
3. **Run-Order Randomization**: Within each repetition $r \in [0, 6]$, the complete list of 300 parallel configurations is pseudorandomly shuffled using a fixed seed ($S = 42$). This prevents systematic bias arising from CPU frequency boost decay, thermal buildup, background OS daemon scheduling, or loop ordering effects.

---

## 7. Metrics and Statistical Formulas

### 7.1 Point Estimates and Dispersion
Given repeated measurements $T_{1}, T_{2}, \dots, T_{k}$ ($k=7$) for a configuration:
- **Median Runtime**: Main robust point estimate $\tilde{T} = \text{median}(T_{1}, \dots, T_{k})$.
- **Sample Mean**: $\bar{T} = \frac{1}{k} \sum_{i=1}^k T_i$.
- **Sample Standard Deviation**: $s = \sqrt{\frac{1}{k-1} \sum_{i=1}^k (T_i - \bar{T})^2}$.

### 7.2 Parallel Speedup
For a given workload $w$, scheduling configuration $c$, and thread count $P$:
$$S_p(w, c, P) = \frac{\tilde{T}_{\text{serial}}(w)}{\tilde{T}_{\text{parallel}}(w, c, P)}$$
Where $\tilde{T}_{\text{serial}}(w)$ is the median execution time of a genuine standalone serial implementation compiled without OpenMP pragmas.

### 7.3 Parallel Efficiency
$$E_p(w, c, P) = \frac{S_p(w, c, P)}{P}$$

### 7.4 Relative Performance vs. Default Static
$$\Delta T_{\text{rel}}(w, c, P) = \frac{\tilde{T}_{\text{static\_default}}(w, P) - \tilde{T}(w, c, P)}{\tilde{T}_{\text{static\_default}}(w, P)} \times 100\%$$
- $\Delta T_{\text{rel}} > 0$: Configuration $c$ outperforms default static scheduling by $\Delta T_{\text{rel}}\%$.
- $\Delta T_{\text{rel}} < 0$: Configuration $c$ regresses relative to default static scheduling.

### 7.5 Bootstrap Confidence Intervals
Confidence intervals (95%) for medians and speedup ratios are calculated non-parametrically using $B = 2000$ bootstrap resamples with replacement.
For speedup $S_p = \tilde{T}_s / \tilde{T}_p$, uncertainty in both serial baseline measurements and parallel runs is preserved simultaneously:
$$\text{BootSpeedup}_b = \frac{\text{median}(T_{s, b}^*)}{\text{median}(T_{p, b}^*)}$$
The 95% confidence interval is extracted via the 2.5th and 97.5th percentiles of the bootstrap distribution.
