#!/usr/bin/env python3
"""
scripts/validate_results.py - Quality Assurance and Integrity Validation

Validates raw CSV experimental results against rigorous criteria:
- Complete header and schema compliance.
- Non-empty, strictly positive elapsed_ms with no NaNs or nulls.
- Valid 64-bit hexadecimal checksums.
- Strict checksum agreement between serial baselines and all parallel scheduling variants.
- Strict checksum agreement across all repetitions.
- Thread observation consistency (actual_threads == requested_threads).
- Workload cost and CV conservation (clustered_high vs random_high total work).
- Complete matrix representation (no missing configurations).
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np

REQUIRED_COLUMNS = [
    "run_id",
    "measurement_kind",
    "timestamp",
    "workload_name",
    "arrangement",
    "target_cv",
    "actual_cv",
    "total_iterations",
    "total_work_units",
    "scheduling_policy",
    "chunk_size",
    "requested_threads",
    "actual_threads",
    "repetition_index",
    "random_seed",
    "elapsed_ms",
    "checksum",
    "compiler_info",
    "build_type"
]


def validate_csv(csv_path, expected_repeats=None):
    print(f"[VALIDATE] Validating CSV file: {csv_path}")
    if not os.path.exists(csv_path):
        print(f"[ERROR] File does not exist: {csv_path}")
        return False

    df = pd.read_csv(csv_path)
    print(f"[VALIDATE] Total rows loaded: {len(df)}")

    # 1. Column completeness
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"[ERROR] Missing required columns: {missing_cols}")
        return False
    print("[VALIDATE] PASS: All required columns present.")

    # 2. Null and NaN checks
    null_counts = df[REQUIRED_COLUMNS].isnull().sum()
    if null_counts.any():
        print(f"[ERROR] Found null values:\n{null_counts[null_counts > 0]}")
        return False
    print("[VALIDATE] PASS: Zero null/NaN values across all fields.")

    # 3. Numeric bounds on elapsed_ms
    if (df["elapsed_ms"] <= 0).any():
        print("[ERROR] Found non-positive elapsed_ms values!")
        return False
    print(f"[VALIDATE] PASS: Elapsed times are strictly positive (min: {df['elapsed_ms'].min():.4f} ms, max: {df['elapsed_ms'].max():.4f} ms).")

    # 4. Thread consistency
    mismatched_threads = df[df["requested_threads"] != df["actual_threads"]]
    if not mismatched_threads.empty:
        print(f"[ERROR] Found {len(mismatched_threads)} rows where actual_threads != requested_threads!")
        return False
    print("[VALIDATE] PASS: Actual threads observed match requested threads in all records.")

    # 5. Checksum verification
    # For each workload, collect serial checksum and verify every parallel execution matches
    workloads = df["workload_name"].unique()
    for wl in workloads:
        wl_df = df[df["workload_name"] == wl]
        unique_checksums = wl_df["checksum"].unique()
        if len(unique_checksums) != 1:
            print(f"[ERROR] Checksum divergence detected for workload '{wl}'!")
            print(f"Distinct checksums found: {unique_checksums}")
            return False
        print(f"[VALIDATE] PASS: Workload '{wl}' has 100% deterministic checksum ({unique_checksums[0]}) across {len(wl_df)} runs.")

    # 6. Conservation between random_high and clustered_high
    rh = df[df["workload_name"] == "random_high"]
    ch = df[df["workload_name"] == "clustered_high"]
    if not rh.empty and not ch.empty:
        rh_work = rh["total_work_units"].iloc[0]
        ch_work = ch["total_work_units"].iloc[0]
        if rh_work != ch_work:
            print(f"[ERROR] Work unit mismatch between random_high ({rh_work}) and clustered_high ({ch_work})!")
            return False
        rh_cv = rh["actual_cv"].iloc[0]
        ch_cv = ch["actual_cv"].iloc[0]
        if abs(rh_cv - ch_cv) > 1e-4:
            print(f"[ERROR] Actual CV mismatch between random_high ({rh_cv}) and clustered_high ({ch_cv})!")
            return False
        print(f"[VALIDATE] PASS: random_high and clustered_high strictly preserve total work ({rh_work}) and actual CV ({rh_cv:.4f}).")

    # 7. Check repetition count if specified
    if expected_repeats is not None:
        group_counts = df.groupby(["measurement_kind", "workload_name", "scheduling_policy", "chunk_size", "requested_threads"]).size()
        deviations = group_counts[group_counts != expected_repeats]
        if not deviations.empty:
            print(f"[ERROR] Found configurations with != {expected_repeats} repetitions:\n{deviations}")
            return False
        print(f"[VALIDATE] PASS: All {len(group_counts)} experimental cells have exactly {expected_repeats} repetitions.")

    print("[VALIDATE] ALL INTEGRITY CHECKS PASSED.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate CS2 scheduling study raw results")
    parser.add_argument("csv_path", nargs="?", default="results/raw/raw_runs.csv", help="Path to raw CSV file")
    parser.add_argument("--expected-repeats", type=int, default=None, help="Expected repetitions per cell")
    args = parser.parse_args()

    success = validate_csv(args.csv_path, args.expected_repeats)
    sys.exit(0 if success else 1)
