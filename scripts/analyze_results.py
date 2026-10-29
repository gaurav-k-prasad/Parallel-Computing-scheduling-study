#!/usr/bin/env python3
"""
scripts/analyze_results.py - Statistical Analysis and Figure Generation

Loads raw experimental measurements from results/raw/raw_runs.csv,
computes robust summary statistics, bootstrap confidence intervals,
speedup, parallel efficiency, dispatch probe overhead proxies, and
relative policy comparisons.

Generates publication-quality figures in both PNG (300 DPI) and PDF formats:
1. Fig 1: Execution Time vs. Thread Count (small multiples across workloads)
2. Fig 2: Parallel Speedup vs. Thread Count (with ideal linear reference)
3. Fig 3: Dispatch Overhead Proxy vs. Workload Irregularity (CV)
4. Fig 4: Parallel Efficiency vs. Thread Count
5. Fig 5: Execution Time vs. Workload CV (at key thread counts)
6. Fig 6: Chunk-Size Sensitivity (Static, Dynamic, Guided)
7. Fig 7: Spatial Locality Impact: Randomized vs. Clustered High Irregularity
8. Fig 8: Dispatch Overhead Proxy vs. Chunk Size
9. Fig 9: Mandelbrot Benchmark Execution Time and Speedup
10. Fig 10: Relative Performance Heatmap (% Speedup over Default Static)
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_RAW_DIR = os.path.join(PROJECT_ROOT, "results", "raw")
RESULTS_PROC_DIR = os.path.join(PROJECT_ROOT, "results", "processed")
FIGURES_PNG_DIR = os.path.join(PROJECT_ROOT, "figures", "png")
FIGURES_PDF_DIR = os.path.join(PROJECT_ROOT, "figures", "pdf")

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "lines.linewidth": 1.8,
    "lines.markersize": 6,
    "figure.autolayout": True
})

POLICY_COLORS = {
    "static_default": "#1f77b4",
    "static_c1": "#aec7e8",
    "static_c8": "#4a7bb0",
    "static_c64": "#084081",
    "dynamic_c1": "#ff7f0e",
    "dynamic_c8": "#d95f02",
    "dynamic_c64": "#8c2d04",
    "guided_c1": "#2ca02c",
    "guided_c8": "#31a354",
    "guided_c64": "#006d2c"
}

POLICY_LABELS = {
    "static_default": "Static (Default)",
    "static_c1": "Static (Chunk 1)",
    "static_c8": "Static (Chunk 8)",
    "static_c64": "Static (Chunk 64)",
    "dynamic_c1": "Dynamic (Chunk 1)",
    "dynamic_c8": "Dynamic (Chunk 8)",
    "dynamic_c64": "Dynamic (Chunk 64)",
    "guided_c1": "Guided (Chunk 1)",
    "guided_c8": "Guided (Chunk 8)",
    "guided_c64": "Guided (Chunk 64)"
}


def bootstrap_ci(data, stat_fn=np.median, n_boot=2000, ci=0.95, seed=42):
    """Computes two-sided bootstrap confidence interval for arbitrary statistic."""
    rng = np.random.default_rng(seed)
    n = len(data)
    if n <= 1:
        val = stat_fn(data)
        return val, val
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(data, size=n, replace=True)
        boot_stats[i] = stat_fn(sample)
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_stats, 100 * alpha)
    high = np.percentile(boot_stats, 100 * (1.0 - alpha))
    return low, high


def bootstrap_speedup_ci(serial_samples, parallel_samples, n_boot=2000, ci=0.95, seed=42):
    """Computes bootstrap confidence interval for ratio of medians."""
    rng = np.random.default_rng(seed)
    ns = len(serial_samples)
    np_ = len(parallel_samples)
    boot_speedups = np.empty(n_boot)
    for i in range(n_boot):
        s_sample = rng.choice(serial_samples, size=ns, replace=True)
        p_sample = rng.choice(parallel_samples, size=np_, replace=True)
        med_s = np.median(s_sample)
        med_p = np.median(p_sample)
        boot_speedups[i] = med_s / med_p if med_p > 0 else 0
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_speedups, 100 * alpha)
    high = np.percentile(boot_speedups, 100 * (1.0 - alpha))
    return low, high


def save_plot(fig, name):
    png_path = os.path.join(FIGURES_PNG_DIR, f"{name}.png")
    pdf_path = os.path.join(FIGURES_PDF_DIR, f"{name}.pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[FIGURE] Saved {name} (PNG & PDF)")


def analyze_dataset(raw_csv_path):
    print(f"[ANALYZE] Loading raw data: {raw_csv_path}")
    df = pd.read_csv(raw_csv_path)

    os.makedirs(RESULTS_PROC_DIR, exist_ok=True)
    os.makedirs(FIGURES_PNG_DIR, exist_ok=True)
    os.makedirs(FIGURES_PDF_DIR, exist_ok=True)

    # 1. Serial Baseline Medians
    serial_df = df[df["measurement_kind"] == "serial"]
    serial_stats = {}
    for wl, group in serial_df.groupby("workload_name"):
        times = group["elapsed_ms"].values
        low_ci, high_ci = bootstrap_ci(times, np.median)
        serial_stats[wl] = {
            "median_ms": np.median(times),
            "mean_ms": np.mean(times),
            "std_ms": np.std(times, ddof=1) if len(times) > 1 else 0.0,
            "low_ci": low_ci,
            "high_ci": high_ci,
            "samples": times
        }

    # 2. Workload Cost Statistics table
    wl_rows = []
    for wl, group in df.groupby("workload_name"):
        row0 = group.iloc[0]
        wl_rows.append({
            "workload_name": wl,
            "arrangement": row0["arrangement"],
            "target_cv": row0["target_cv"],
            "actual_cv": row0["actual_cv"],
            "total_iterations": row0["total_iterations"],
            "total_work_units": row0["total_work_units"],
            "serial_median_ms": serial_stats.get(wl, {}).get("median_ms", 0.0),
            "serial_std_ms": serial_stats.get(wl, {}).get("std_ms", 0.0)
        })
    wl_df = pd.DataFrame(wl_rows)
    wl_df.to_csv(os.path.join(RESULTS_PROC_DIR, "workload_statistics.csv"), index=False)

    # 3. Dispatch Probes
    probe_df = df[df["measurement_kind"] == "dispatch_probe"]
    probe_summary = []
    for (pol, chunk, th), group in probe_df.groupby(["scheduling_policy", "chunk_size", "requested_threads"]):
        times = group["elapsed_ms"].values
        low_ci, high_ci = bootstrap_ci(times, np.median)
        key = pol if chunk == "default" else f"{pol}_c{chunk}"
        probe_summary.append({
            "scheduling_policy": pol,
            "chunk_size": chunk,
            "config_key": key,
            "requested_threads": th,
            "sample_count": len(times),
            "probe_median_ms": np.median(times),
            "probe_mean_ms": np.mean(times),
            "probe_std_ms": np.std(times, ddof=1) if len(times) > 1 else 0.0,
            "probe_low_ci": low_ci,
            "probe_high_ci": high_ci
        })
    probe_summary_df = pd.DataFrame(probe_summary)
    probe_summary_df.to_csv(os.path.join(RESULTS_PROC_DIR, "overhead.csv"), index=False)

    # 4. Parallel Workloads Analysis
    par_df = df[df["measurement_kind"] == "workload"]
    summary_rows = []
    speedup_rows = []
    efficiency_rows = []

    # Map probe times for relative overhead calculation
    probe_map = {}
    for _, r in probe_summary_df.iterrows():
        probe_map[(r["scheduling_policy"], str(r["chunk_size"]), int(r["requested_threads"]))] = r["probe_median_ms"]

    grouped = par_df.groupby(["workload_name", "scheduling_policy", "chunk_size", "requested_threads"])

    for (wl, pol, chunk, th), group in grouped:
        times = group["elapsed_ms"].values
        med_t = np.median(times)
        mean_t = np.mean(times)
        std_t = np.std(times, ddof=1) if len(times) > 1 else 0.0
        min_t = np.min(times)
        max_t = np.max(times)
        low_ci, high_ci = bootstrap_ci(times, np.median)

        cfg_key = pol if chunk == "default" else f"{pol}_c{chunk}"

        # Speedup & Efficiency
        s_med = serial_stats[wl]["median_ms"]
        s_samples = serial_stats[wl]["samples"]
        speedup = s_med / med_t if med_t > 0 else 0
        sp_low_ci, sp_high_ci = bootstrap_speedup_ci(s_samples, times)
        efficiency = speedup / th
        eff_low_ci = sp_low_ci / th
        eff_high_ci = sp_high_ci / th

        # Dispatch probe proxy
        probe_med = probe_map.get((pol, str(chunk), int(th)), 0.0)
        overhead_pct = (probe_med / med_t * 100.0) if med_t > 0 else 0.0

        target_cv = group["target_cv"].iloc[0]
        actual_cv = group["actual_cv"].iloc[0]
        arrangement = group["arrangement"].iloc[0]

        summary_rows.append({
            "workload_name": wl,
            "arrangement": arrangement,
            "target_cv": target_cv,
            "actual_cv": actual_cv,
            "scheduling_policy": pol,
            "chunk_size": chunk,
            "config_key": cfg_key,
            "requested_threads": th,
            "sample_count": len(times),
            "median_ms": med_t,
            "mean_ms": mean_t,
            "std_ms": std_t,
            "min_ms": min_t,
            "max_ms": max_t,
            "time_ci95_low": low_ci,
            "time_ci95_high": high_ci,
            "serial_median_ms": s_med,
            "speedup": speedup,
            "speedup_ci95_low": sp_low_ci,
            "speedup_ci95_high": sp_high_ci,
            "efficiency": efficiency,
            "efficiency_ci95_low": eff_low_ci,
            "efficiency_ci95_high": eff_high_ci,
            "probe_overhead_ms": probe_med,
            "probe_overhead_pct": overhead_pct
        })

    summary_df = pd.DataFrame(summary_rows)

    # 5. Relative Performance against Static Default
    # Relative % = (T_static_default - T_policy) / T_static_default * 100
    # Positive means policy is faster (improvement), negative means slower (regression)
    static_def_map = {}
    for _, r in summary_df[summary_df["config_key"] == "static_default"].iterrows():
        static_def_map[(r["workload_name"], int(r["requested_threads"]))] = r["median_ms"]

    rel_pcts = []
    for _, r in summary_df.iterrows():
        base_t = static_def_map.get((r["workload_name"], int(r["requested_threads"])), np.nan)
        if pd.notna(base_t) and base_t > 0:
            rel = (base_t - r["median_ms"]) / base_t * 100.0
        else:
            rel = 0.0
        rel_pcts.append(rel)
    summary_df["relative_improvement_pct"] = rel_pcts

    # Save summary tables
    summary_df.to_csv(os.path.join(RESULTS_PROC_DIR, "summary.csv"), index=False)

    speedup_df = summary_df[["workload_name", "config_key", "requested_threads", "speedup", "speedup_ci95_low", "speedup_ci95_high"]]
    speedup_df.to_csv(os.path.join(RESULTS_PROC_DIR, "speedup.csv"), index=False)

    efficiency_df = summary_df[["workload_name", "config_key", "requested_threads", "efficiency", "efficiency_ci95_low", "efficiency_ci95_high"]]
    efficiency_df.to_csv(os.path.join(RESULTS_PROC_DIR, "efficiency.csv"), index=False)

    # Save analysis metadata
    meta = {
        "analysis_timestamp": pd.Timestamp.now().isoformat(),
        "total_records_processed": len(df),
        "total_summary_cells": len(summary_df),
        "workloads": list(summary_df["workload_name"].unique()),
        "scheduling_configs": list(summary_df["config_key"].unique()),
        "thread_counts": [int(x) for x in sorted(summary_df["requested_threads"].unique())],
        "bootstrap_iterations": 2000,
        "confidence_level": 0.95
    }
    with open(os.path.join(RESULTS_PROC_DIR, "analysis_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("[ANALYZE] Generated all processed summary CSVs.")
    return summary_df, probe_summary_df, wl_df


def generate_figures(summary_df, probe_summary_df, wl_df):
    print("[FIGURES] Generating publication-quality figures...")

    # Filter representative configs for cleaner graphs when needed
    key_configs = [
        "static_default",
        "static_c1",
        "static_c64",
        "dynamic_c1",
        "dynamic_c8",
        "dynamic_c64",
        "guided_c1",
        "guided_c64"
    ]

    thread_counts = sorted(summary_df["requested_threads"].unique())

    # =========================================================================
    # MANDATORY FIGURE 1: Execution Time vs Thread Count (Small Multiples)
    # =========================================================================
    synth_workloads = ["regular", "random_low", "random_med", "random_high", "clustered_high"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), sharey=False)
    axes = axes.flatten()

    all_workloads = synth_workloads + ["mandelbrot"]
    wl_titles = {
        "regular": "Regular (CV = 0.0)",
        "random_low": "Randomized Low (CV ≈ 0.25)",
        "random_med": "Randomized Med (CV ≈ 0.50)",
        "random_high": "Randomized High (CV ≈ 1.00)",
        "clustered_high": "Clustered High (CV ≈ 1.00, Clustered)",
        "mandelbrot": "Mandelbrot Fractal (Esc. Count CV ≈ 1.67)"
    }

    for idx, wl in enumerate(all_workloads):
        ax = axes[idx]
        sub = summary_df[summary_df["workload_name"] == wl]
        for cfg in key_configs:
            cfg_data = sub[sub["config_key"] == cfg].sort_values("requested_threads")
            if not cfg_data.empty:
                yerr = [
                    cfg_data["median_ms"] - cfg_data["time_ci95_low"],
                    cfg_data["time_ci95_high"] - cfg_data["median_ms"]
                ]
                ax.errorbar(
                    cfg_data["requested_threads"],
                    cfg_data["median_ms"],
                    yerr=yerr,
                    label=POLICY_LABELS.get(cfg, cfg),
                    color=POLICY_COLORS.get(cfg, "#333333"),
                    marker="o",
                    capsize=3,
                    alpha=0.9
                )
        ax.set_title(wl_titles.get(wl, wl), fontweight="bold")
        ax.set_xlabel("Thread Count")
        ax.set_ylabel("Execution Time (ms)")
        ax.set_xticks(thread_counts)
        ax.set_yscale("log")
        ax.grid(True, which="both", ls="--", alpha=0.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.05), frameon=True)
    fig.suptitle("Figure 1: Execution Time vs. Thread Count Across Workload Profiles", fontsize=15, fontweight="bold")
    save_plot(fig, "fig1_execution_time_vs_threads")

    # =========================================================================
    # MANDATORY FIGURE 2: Speedup vs Thread Count (With Ideal Reference)
    # =========================================================================
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), sharey=True)
    axes = axes.flatten()

    for idx, wl in enumerate(all_workloads):
        ax = axes[idx]
        sub = summary_df[summary_df["workload_name"] == wl]
        # Ideal linear speedup line
        ax.plot(thread_counts, thread_counts, "k--", label="Ideal Linear", alpha=0.7, lw=1.5)

        for cfg in key_configs:
            cfg_data = sub[sub["config_key"] == cfg].sort_values("requested_threads")
            if not cfg_data.empty:
                yerr = [
                    cfg_data["speedup"] - cfg_data["speedup_ci95_low"],
                    cfg_data["speedup_ci95_high"] - cfg_data["speedup"]
                ]
                ax.errorbar(
                    cfg_data["requested_threads"],
                    cfg_data["speedup"],
                    yerr=yerr,
                    label=POLICY_LABELS.get(cfg, cfg),
                    color=POLICY_COLORS.get(cfg, "#333333"),
                    marker="s",
                    capsize=3,
                    alpha=0.9
                )
        ax.set_title(wl_titles.get(wl, wl), fontweight="bold")
        ax.set_xlabel("Thread Count")
        ax.set_ylabel("Parallel Speedup (S_p)")
        ax.set_xticks(thread_counts)
        ax.grid(True, which="both", ls="--", alpha=0.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.05), frameon=True)
    fig.suptitle("Figure 2: Parallel Speedup vs. Thread Count Relative to Serial Reference", fontsize=15, fontweight="bold")
    save_plot(fig, "fig2_speedup_vs_threads")

    # =========================================================================
    # MANDATORY FIGURE 3: Scheduling Overhead vs Irregularity
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Left: Dispatch probe absolute time vs actual CV for 16 threads
    # (Note: probe is measured across identical iterations; CV variation comes from workload)
    # We plot probe time for all policies at 8 and 16 threads
    t_targets = [8, 16]
    for th in t_targets:
        sub_probe = probe_summary_df[probe_summary_df["requested_threads"] == th]
        xs = range(len(sub_probe))
        ax1.plot(
            sub_probe["config_key"],
            sub_probe["probe_median_ms"],
            marker="o",
            label=f"{th} Threads",
            lw=2
        )
    ax1.set_title("Low-Work Dispatch Probe Time Across Schedules", fontweight="bold")
    ax1.set_xlabel("Scheduling Policy & Chunk Configuration")
    ax1.set_ylabel("Probe Elapsed Time (ms)")
    ax1.set_yscale("log")
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend()
    ax1.grid(True, which="both", ls="--", alpha=0.5)

    # Right: Dispatch probe as % of workload execution time vs actual CV (at 16 threads)
    sub16 = summary_df[(summary_df["requested_threads"] == 16) & (summary_df["workload_name"].isin(synth_workloads))]
    for cfg in ["static_default", "dynamic_c1", "dynamic_c64", "guided_c1", "guided_c64"]:
        c_data = sub16[sub16["config_key"] == cfg].sort_values("actual_cv")
        if not c_data.empty:
            ax2.plot(
                c_data["actual_cv"],
                c_data["probe_overhead_pct"],
                marker="^",
                label=POLICY_LABELS.get(cfg, cfg),
                color=POLICY_COLORS.get(cfg, "#333333"),
                lw=2
            )
    ax2.set_title("Dispatch Overhead Ratio vs. Workload Irregularity (16 Threads)", fontweight="bold")
    ax2.set_xlabel("Actual Coefficient of Variation (CV)")
    ax2.set_ylabel("Dispatch Probe / Workload Runtime (%)")
    ax2.set_yscale("log")
    ax2.legend()
    ax2.grid(True, which="both", ls="--", alpha=0.5)

    fig.suptitle("Figure 3: Low-Work Scheduling/Dispatch Overhead Proxy Analysis", fontsize=14, fontweight="bold")
    save_plot(fig, "fig3_scheduling_overhead_vs_irregularity")

    # =========================================================================
    # FIGURE 4: Parallel Efficiency vs Thread Count
    # =========================================================================
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), sharey=True)
    axes = axes.flatten()

    for idx, wl in enumerate(all_workloads):
        ax = axes[idx]
        sub = summary_df[summary_df["workload_name"] == wl]
        ax.axhline(1.0, color="k", linestyle="--", alpha=0.6, label="Ideal (100%)")

        for cfg in key_configs:
            cfg_data = sub[sub["config_key"] == cfg].sort_values("requested_threads")
            if not cfg_data.empty:
                ax.plot(
                    cfg_data["requested_threads"],
                    cfg_data["efficiency"] * 100.0,
                    label=POLICY_LABELS.get(cfg, cfg),
                    color=POLICY_COLORS.get(cfg, "#333333"),
                    marker="o",
                    alpha=0.9
                )
        ax.set_title(wl_titles.get(wl, wl), fontweight="bold")
        ax.set_xlabel("Thread Count")
        ax.set_ylabel("Parallel Efficiency (%)")
        ax.set_xticks(thread_counts)
        ax.grid(True, which="both", ls="--", alpha=0.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.05), frameon=True)
    fig.suptitle("Figure 4: Parallel Efficiency (%) vs. Thread Count", fontsize=15, fontweight="bold")
    save_plot(fig, "fig4_efficiency_vs_threads")

    # =========================================================================
    # FIGURE 5: Execution Time vs Workload CV (at Representative Thread Counts)
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, th in zip([ax1, ax2], [8, 16]):
        sub_th = summary_df[(summary_df["requested_threads"] == th) & (summary_df["workload_name"].isin(synth_workloads))]
        for cfg in key_configs:
            c_data = sub_th[sub_th["config_key"] == cfg].sort_values("actual_cv")
            # Separate randomized from clustered
            rand_data = c_data[c_data["arrangement"] != "clustered"]
            if not rand_data.empty:
                ax.plot(
                    rand_data["actual_cv"],
                    rand_data["median_ms"],
                    marker="o",
                    label=POLICY_LABELS.get(cfg, cfg),
                    color=POLICY_COLORS.get(cfg, "#333333")
                )
        ax.set_title(f"Execution Time vs. CV ({th} Threads, Randomized Work)", fontweight="bold")
        ax.set_xlabel("Actual Coefficient of Variation (CV)")
        ax.set_ylabel("Execution Time (ms)")
        ax.grid(True, ls="--", alpha=0.5)

    ax1.legend(loc="upper left", fontsize=9)
    fig.suptitle("Figure 5: Impact of Workload Irregularity (CV) on Execution Time", fontsize=14, fontweight="bold")
    save_plot(fig, "fig5_runtime_vs_workload_cv")

    # =========================================================================
    # FIGURE 6: Chunk-Size Sensitivity for Static, Dynamic, Guided
    # =========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    policies = ["static", "dynamic", "guided"]
    chunk_sizes = [1, 8, 64]

    # Evaluate chunk size on high-irregularity workload at 16 threads
    target_wl = "random_high"
    sub_chunk = summary_df[(summary_df["workload_name"] == target_wl) & (summary_df["requested_threads"] == 16)]

    for idx, pol in enumerate(policies):
        ax = axes[idx]
        times = []
        for c in chunk_sizes:
            cfg_name = f"{pol}_c{c}"
            row = sub_chunk[sub_chunk["config_key"] == cfg_name]
            times.append(row["median_ms"].iloc[0] if not row.empty else np.nan)
        ax.bar([str(c) for c in chunk_sizes], times, color=["#3182bd", "#6baed6", "#9ecae1"], edgecolor="black")
        ax.set_title(f"{pol.capitalize()} Scheduling", fontweight="bold")
        ax.set_xlabel("Chunk Size")
        ax.set_ylabel("Execution Time (ms)")
        ax.grid(True, axis="y", ls="--", alpha=0.5)

    fig.suptitle(f"Figure 6: Chunk-Size Sensitivity on High-Irregularity Workload (CV ≈ 1.0, 16 Threads)", fontsize=14, fontweight="bold")
    save_plot(fig, "fig6_chunk_size_sensitivity")

    # =========================================================================
    # FIGURE 7: Spatial Locality Impact: Randomized vs Clustered High Irregularity
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    comp_sub = summary_df[summary_df["workload_name"].isin(["random_high", "clustered_high"])]

    for ax, th in zip([ax1, ax2], [8, 16]):
        th_data = comp_sub[comp_sub["requested_threads"] == th]
        x_indices = np.arange(len(key_configs))
        width = 0.35

        rand_times = [th_data[(th_data["workload_name"] == "random_high") & (th_data["config_key"] == k)]["median_ms"].iloc[0] for k in key_configs]
        clust_times = [th_data[(th_data["workload_name"] == "clustered_high") & (th_data["config_key"] == k)]["median_ms"].iloc[0] for k in key_configs]

        ax.bar(x_indices - width/2, rand_times, width, label="Randomized High (CV=1.00)", color="#4575b4", edgecolor="black")
        ax.bar(x_indices + width/2, clust_times, width, label="Clustered High (CV=1.00)", color="#d73027", edgecolor="black")

        ax.set_xticks(x_indices)
        ax.set_xticklabels([POLICY_LABELS.get(k, k).replace(" ", "\n") for k in key_configs], rotation=45, ha="right")
        ax.set_title(f"Randomized vs. Clustered Comparison ({th} Threads)", fontweight="bold")
        ax.set_ylabel("Execution Time (ms)")
        ax.grid(True, axis="y", ls="--", alpha=0.5)
        ax.legend()

    fig.suptitle("Figure 7: Impact of Spatial Arrangement under Identical CV and Equal Total Work", fontsize=14, fontweight="bold")
    save_plot(fig, "fig7_spatial_clustering_comparison")

    # =========================================================================
    # FIGURE 8: Dispatch Overhead Proxy vs Chunk Size
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, th in zip([ax1, ax2], [8, 16]):
        p_th = probe_summary_df[probe_summary_df["requested_threads"] == th]
        for pol in ["static", "dynamic", "guided"]:
            c_times = []
            for c in [1, 8, 64]:
                r = p_th[(p_th["scheduling_policy"] == pol) & (p_th["chunk_size"] == str(c))]
                c_times.append(r["probe_median_ms"].iloc[0] if not r.empty else np.nan)
            ax.plot([1, 8, 64], c_times, marker="o", lw=2, label=pol.capitalize())
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks([1, 8, 64])
        ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
        ax.set_title(f"Dispatch Probe Time vs. Chunk Size ({th} Threads)", fontweight="bold")
        ax.set_xlabel("Chunk Size (log2 scale)")
        ax.set_ylabel("Probe Elapsed Time (ms, log scale)")
        ax.grid(True, which="both", ls="--", alpha=0.5)
        ax.legend()

    fig.suptitle("Figure 8: Low-Work Dispatch Probe Overhead as a Function of Chunk Size", fontsize=14, fontweight="bold")
    save_plot(fig, "fig8_dispatch_overhead_vs_chunk_size")

    # =========================================================================
    # FIGURE 9: Mandelbrot Benchmark Execution Time and Speedup
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    m_sub = summary_df[summary_df["workload_name"] == "mandelbrot"]

    for cfg in key_configs:
        m_cfg = m_sub[m_sub["config_key"] == cfg].sort_values("requested_threads")
        if not m_cfg.empty:
            ax1.plot(m_cfg["requested_threads"], m_cfg["median_ms"], marker="o", label=POLICY_LABELS.get(cfg, cfg), color=POLICY_COLORS.get(cfg, "#333333"))
            ax2.plot(m_cfg["requested_threads"], m_cfg["speedup"], marker="s", label=POLICY_LABELS.get(cfg, cfg), color=POLICY_COLORS.get(cfg, "#333333"))

    ax1.set_title("Mandelbrot Execution Time vs. Threads", fontweight="bold")
    ax1.set_xlabel("Thread Count")
    ax1.set_ylabel("Execution Time (ms)")
    ax1.set_xticks(thread_counts)
    ax1.grid(True, ls="--", alpha=0.5)

    ax2.plot(thread_counts, thread_counts, "k--", label="Ideal Linear", alpha=0.7)
    ax2.set_title("Mandelbrot Parallel Speedup vs. Threads", fontweight="bold")
    ax2.set_xlabel("Thread Count")
    ax2.set_ylabel("Parallel Speedup (S_p)")
    ax2.set_xticks(thread_counts)
    ax2.grid(True, ls="--", alpha=0.5)
    ax2.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))

    fig.suptitle("Figure 9: Mandelbrot Fractal Benchmark Scaling and Speedup", fontsize=14, fontweight="bold")
    save_plot(fig, "fig9_mandelbrot_results")

    # =========================================================================
    # FIGURE 10: Heatmap of Relative Improvement Over Default Static
    # =========================================================================
    # Select Dynamic Chunk 1 and Guided Chunk 8 relative to Static Default across workloads and threads
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    target_wls = ["regular", "random_low", "random_med", "random_high", "clustered_high", "mandelbrot"]
    wl_display = ["Regular\n(CV=0)", "Rand Low\n(CV=0.25)", "Rand Med\n(CV=0.50)", "Rand High\n(CV=1.00)", "Clustered High\n(CV=1.00)", "Mandelbrot\n(CV=1.67)"]

    for ax, comp_cfg, title in [(ax1, "dynamic_c1", "Dynamic (Chunk 1)"), (ax2, "guided_c8", "Guided (Chunk 8)")]:
        matrix = np.zeros((len(target_wls), len(thread_counts)))
        for i, wl in enumerate(target_wls):
            for j, th in enumerate(thread_counts):
                r = summary_df[(summary_df["workload_name"] == wl) & (summary_df["config_key"] == comp_cfg) & (summary_df["requested_threads"] == th)]
                if not r.empty:
                    matrix[i, j] = r["relative_improvement_pct"].iloc[0]

        # Symmetric diverging colormap centered at 0%
        vmax = max(abs(matrix.min()), abs(matrix.max()))
        vmax = max(vmax, 5.0) # avoid division by zero
        cax = ax.imshow(matrix, cmap="coolwarm_r", vmin=-vmax, vmax=vmax, aspect="auto")

        # Overlay text
        for i in range(len(target_wls)):
            for j in range(len(thread_counts)):
                val = matrix[i, j]
                color = "white" if abs(val) > vmax * 0.55 else "black"
                ax.text(j, i, f"{val:+.1f}%", ha="center", va="center", color=color, fontweight="bold", fontsize=9)

        ax.set_xticks(range(len(thread_counts)))
        ax.set_xticklabels([f"{t} Threads" for t in thread_counts])
        ax.set_yticks(range(len(target_wls)))
        ax.set_yticklabels(wl_display)
        ax.set_title(f"{title} vs. Default Static", fontweight="bold")
        cbar = fig.colorbar(cax, ax=ax, orientation="horizontal", pad=0.15)
        cbar.set_label("Relative Speedup (%) [Positive = Faster than Static Default]")

    fig.suptitle("Figure 10: Relative Performance Gain/Loss vs. Default Static Scheduling", fontsize=15, fontweight="bold")
    save_plot(fig, "fig10_relative_performance_heatmap")

    print("[FIGURES] All 10 figures successfully created in figures/png/ and figures/pdf/.")


def main():
    parser = argparse.ArgumentParser(description="Analyze CS2 OpenMP Scheduling Experiment Results")
    parser.add_argument("raw_csv", nargs="?", default=os.path.join(RESULTS_RAW_DIR, "raw_runs.csv"), help="Path to raw CSV file")
    args = parser.parse_args()

    summary_df, probe_summary_df, wl_df = analyze_dataset(args.raw_csv)
    generate_figures(summary_df, probe_summary_df, wl_df)
    print("[ANALYZE] Analysis complete. All tables and figures updated.")


if __name__ == "__main__":
    main()
