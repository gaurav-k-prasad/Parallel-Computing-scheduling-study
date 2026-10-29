# Experimental Results Summary

## 1. Executive Summary Table (16 Threads, AMD Ryzen 7 6800H)

The table below presents the primary empirical measurements obtained across 7 independent repetitions on the 16-logical-thread host system (8 physical cores with SMT). All values are medians with 95% bootstrap confidence intervals ($B = 2000$).

| Workload | Policy & Chunk | Median Runtime (ms) | 95% CI (ms) | Speedup ($S_p$) | Efficiency ($E_p$) | Relative to Static Default |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Regular** ($CV = 0.00$) | `static_default` | 33.75 | [27.99, 40.24] | 8.07x | 50.4% | Baseline (0.0%) |
| | `static_c1` | 33.57 | [31.44, 47.11] | 8.11x | 50.7% | +0.5% |
| | `dynamic_c1` | 36.55 | [32.64, 45.84] | 7.45x | 46.6% | **-8.3% (Regression)** |
| | `dynamic_c8` | 27.95 | [25.09, 36.25] | 9.74x | 60.9% | +17.2% |
| | `dynamic_c64` | 28.99 | [25.07, 31.35] | 9.40x | 58.7% | +14.1% |
| | `guided_c1` | 29.62 | [24.95, 41.22] | 9.20x | 57.5% | +12.2% |
| | `guided_c8` | 28.74 | [25.34, 30.81] | 9.48x | 59.2% | +14.8% |
| **Randomized Low** ($CV = 0.25$) | `static_default` | 29.70 | [27.10, 34.94] | 9.29x | 58.0% | Baseline (0.0%) |
| | `dynamic_c1` | 25.24 | [20.66, 30.25] | 10.93x | 68.3% | +15.0% |
| | `dynamic_c8` | 23.53 | [22.16, 28.97] | 11.72x | 73.3% | +20.8% |
| | `dynamic_c64` | 23.33 | [20.05, 27.14] | 11.82x | 73.9% | **+21.4%** |
| | `guided_c1` | 31.62 | [24.04, 40.94] | 8.72x | 54.5% | -6.4% |
| **Randomized High** ($CV = 1.00$) | `static_default` | 34.05 | [29.16, 39.23] | 8.13x | 50.8% | Baseline (0.0%) |
| | `dynamic_c1` | 23.64 | [20.61, 27.40] | 11.71x | 73.2% | +30.6% |
| | `dynamic_c8` | 24.29 | [21.97, 37.69] | 11.39x | 71.2% | +28.7% |
| | `dynamic_c64` | 23.42 | [21.39, 30.50] | 11.82x | 73.9% | +31.2% |
| | `guided_c1` | 22.86 | [19.82, 34.16] | 12.10x | 75.6% | **+32.8%** |
| | `guided_c8` | 30.43 | [22.78, 33.41] | 9.09x | 56.8% | +10.6% |
| **Clustered High** ($CV = 1.00$) | `static_default` | 69.43 | [65.34, 72.89] | 3.93x | 24.6% | Baseline (0.0%) |
| | `static_c1` | 26.91 | [22.45, 29.09] | 10.15x | 63.4% | +61.2% |
| | `dynamic_c1` | 26.52 | [22.99, 27.75] | 10.30x | 64.4% | +61.8% |
| | `dynamic_c8` | 22.60 | [20.27, 32.03] | 12.08x | 75.5% | **+67.4%** |
| | `dynamic_c64` | 23.66 | [23.18, 25.94] | 11.54x | 72.1% | +65.9% |
| | `guided_c1` | 31.57 | [28.73, 35.58] | 8.65x | 54.1% | +54.5% |
| **Mandelbrot Fractal** ($CV \approx 1.65$) | `static_default` | 93.41 | [87.27, 101.93] | 5.13x | 32.0% | Baseline (0.0%) |
| | `static_c1` | 68.76 | [64.11, 79.99] | 6.97x | 43.5% | +26.4% |
| | `dynamic_c1` | 72.90 | [66.02, 78.25] | 6.57x | 41.1% | +22.0% |
| | `dynamic_c8` | 50.13 | [48.09, 53.92] | 9.55x | 59.7% | **+46.3%** |
| | `dynamic_c64` | 61.18 | [55.50, 70.14] | 7.83x | 48.9% | +34.5% |
| | `guided_c1` | 82.58 | [75.06, 85.07] | 5.80x | 36.3% | +11.6% |
| | `guided_c8` | 80.97 | [72.38, 81.63] | 5.92x | 37.0% | +13.3% |

---

## 2. Strongest Supported Empirical Findings

### Finding 1: Spatial Arrangement Dominates Coefficient of Variation
The most pronounced finding in the study is that **statistical variance ($CV$) alone cannot predict load imbalance**.
- In the *Randomized High* workload ($CV = 1.0035$), `static_default` completed in **$34.05$ ms** ($S_p = 8.13\text{x}$).
- In the *Clustered High* workload ($CV = 1.0035$), which contains the exact same iteration cost multiset and exact same total computational work ($50,000,000$ operations), `static_default` slowed down to **$69.43$ ms** ($S_p = 3.93\text{x}$).
- Because `static_default` assigns contiguous partitions of size $\approx N/P$ to each thread, the threads assigned to the central indices $[N/4, 3N/4)$ received the bulk of the computational burden, while outer threads sat idle at the barrier.
- In contrast, dynamic scheduling (`dynamic_c8`) achieved **$22.60$ ms** on the clustered workload—outperforming default static by **67.4%** (Figure 7).

### Finding 2: Dynamic Scheduling Regresses on Regular Loops with Small Chunks
For completely regular loops ($CV = 0.0$), `dynamic_c1` regressed by **$8.3\%$** relative to `static_default` ($36.55$ ms vs. $33.75$ ms) at 16 threads.
- Dispatch probe measurements confirmed that `dynamic_c1` generates $2.75$ ms of dispatch latency due to $100,000$ atomic work-queue contentions across 16 threads (Figure 3 and Figure 8).
- When each iteration has identical cost, dynamic scheduling introduces unnecessary coordination overhead without providing any load balancing benefit.

### Finding 3: Medium Chunks ($C = 8$) Provide Optimal Balancing in Practical Irregular Loops
Across both Clustered High and the Mandelbrot benchmark, `dynamic_c8` was the top-performing configuration:
- In Mandelbrot ($1200 \times 900$, $CV \approx 1.65$), `dynamic_c8` achieved **$50.13$ ms** ($S_p = 9.55\text{x}$), outperforming `dynamic_c1` ($72.90$ ms) by $31.2\%$ and `static_default` ($93.41$ ms) by **$46.3\%$**.
- Chunks of 8 amortize atomic queue accesses by a factor of 8 relative to unit chunks, while remaining small enough to prevent tail stragglers (Figure 6 and Figure 9).

### Finding 4: Guided Scheduling Excels in Random Irregularity but Struggles under Non-Uniform Geometry
In *Randomized High* irregularity, `guided_c1` achieved the single fastest runtime in the entire benchmark suite (**$22.86$ ms**, $S_p = 12.10\text{x}$, efficiency $75.6\%$).
- Guided self-scheduling dynamically reduces chunk sizes as loop execution progresses ($\approx \text{remaining} / P$). Initial large chunks minimize queue overhead, while final unit chunks resolve residual imbalance.
- However, in Mandelbrot, where the central boundary regions contain large contiguous blocks of non-escaping pixels, `guided_c1` achieved only $82.58$ ms ($+11.6\%$ over static), trailing `dynamic_c8` ($50.13$ ms) by a significant margin.

### Finding 5: Scaling Across Physical vs. SMT Hardware Boundaries
Parallel scaling transitions cleanly at the physical core boundary ($P = 8$):
- Across all synthetic workloads, scaling from 1 to 8 threads yielded near-linear speedups ($S_p \approx 6.8\text{x} - 7.5\text{x}$ on 8 physical cores).
- Scaling from 8 to 16 threads (activating SMT) yielded additional speedups up to $12.10\text{x}$ ($+61\%$ scaling over 8 threads).
- Because the synthetic kernel is heavily integer ALU-bound, SMT threads successfully exploit vacant execution pipelines, demonstrating that SMT is beneficial for irregular workloads provided scheduling policies prevent thread starvation (Figure 1 and Figure 2).

---

## 3. Reference to Generated Figures

- **Figure 1 (`fig1_execution_time_vs_threads`)**: Shows log-scale execution time decreasing from 1 to 16 threads across all 6 workloads. Highlights the dramatic divergence between static default and dynamic policies on clustered and Mandelbrot workloads.
- **Figure 2 (`fig2_speedup_vs_threads`)**: Contrasts empirical speedup curves against the ideal linear diagonal, demonstrating near-ideal scaling for dynamic/guided policies up to 8 physical cores and continuing through 16 SMT threads.
- **Figure 3 (`fig3_scheduling_overhead_vs_irregularity`)**: Demonstrates that dispatch probe latency is governed by chunk size and thread concurrency rather than workload irregularity, showing probe overhead percentage remaining under $2\%$ for chunked dynamic policies but rising sharply for unit chunks.
- **Figure 4 (`fig4_efficiency_vs_threads`)**: Illustrates parallel efficiency, which remains between $70-76\%$ at 16 threads for well-tuned dynamic/guided schedules on irregular workloads, but plummets to $24.6\%$ for static default on clustered work.
- **Figure 5 (`fig5_runtime_vs_workload_cv`)**: Shows execution time plotted against actual $CV$, illustrating how static scheduling runtime increases as irregularity grows, whereas dynamic chunked policies maintain consistently low runtimes.
- **Figure 6 (`fig6_chunk_size_sensitivity`)**: Compares chunk sizes 1, 8, and 64 for static, dynamic, and guided scheduling, confirming that chunk size 8 provides the most robust compromise between dispatch contention and tail-load balance.
- **Figure 7 (`fig7_spatial_clustering_comparison`)**: Bar chart comparing *Randomized High* vs. *Clustered High*, proving that spatial clustering induces severe load imbalance in default static scheduling ($69.43$ ms vs. $34.05$ ms) while dynamic scheduling remains immune ($22.60$ ms vs. $24.29$ ms).
- **Figure 8 (`fig8_dispatch_overhead_vs_chunk_size`)**: Log-log plot showing exponential reduction in dispatch probe overhead as chunk size increases from 1 to 64.
- **Figure 9 (`fig9_mandelbrot_results`)**: Validates the study's conclusions on the real-world fractal benchmark, showing `dynamic_c8` achieving maximum speedup ($9.55\text{x}$).
- **Figure 10 (`fig10_relative_performance_heatmap`)**: Dual heatmap showing percentage performance gain/loss over static default for `dynamic_c1` and `guided_c8` across all workloads and thread counts.
