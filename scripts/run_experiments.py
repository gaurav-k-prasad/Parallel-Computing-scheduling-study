#!/usr/bin/env python3
"""
scripts/run_experiments.py - Experiment Runner for CS2 Scheduling Study

Orchestrates execution of the experimental matrix:
- Compiles/verifies the benchmark and test binaries.
- Executes correctness checks before running measurements.
- Collects environment metadata (CPU, RAM, OS, compiler, OpenMP, Python).
- Executes genuine serial baselines, parallel workloads, and low-work dispatch probes.
- Applies run-order randomization within each repetition to mitigate thermal and ordering bias.
- Sets OpenMP affinity and execution flags.
- Saves raw data to results/raw/raw_runs.csv and metadata to results/raw/environment.json.
- Logs stdout/stderr to logs/.
"""

import os
import sys
import subprocess
import argparse
import json
import random
import time
import platform
import shutil
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
BENCHMARK_BIN = os.path.join(BUILD_DIR, "benchmark")
TEST_BIN = os.path.join(BUILD_DIR, "correctness_tests")
RESULTS_RAW_DIR = os.path.join(PROJECT_ROOT, "results", "raw")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")


def get_cpu_info():
    info = {
        "model": platform.processor(),
        "arch": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "physical_cores": None,
        "lscpu": {}
    }
    try:
        res = subprocess.run(["lscpu"], capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info["lscpu"][k.strip()] = v.strip()
        if "Model name" in info["lscpu"]:
            info["model"] = info["lscpu"]["Model name"]
        if "Core(s) per socket" in info["lscpu"] and "Socket(s)" in info["lscpu"]:
            cores_per_socket = int(info["lscpu"]["Core(s) per socket"])
            sockets = int(info["lscpu"]["Socket(s)"])
            info["physical_cores"] = cores_per_socket * sockets
    except Exception as e:
        info["lscpu_error"] = str(e)
    return info


def get_memory_info():
    info = {"total_ram_gb": None, "available_ram_gb": None}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if parts[0] == "MemTotal:":
                    info["total_ram_gb"] = round(int(parts[1]) / (1024 * 1024), 2)
                elif parts[0] == "MemAvailable:":
                    info["available_ram_gb"] = round(int(parts[1]) / (1024 * 1024), 2)
    except Exception as e:
        info["meminfo_error"] = str(e)
    return info


def get_compiler_info():
    info = {"compiler": "g++", "version": None, "openmp_version": None}
    try:
        res = subprocess.run(["g++", "--version"], capture_output=True, text=True, check=True)
        info["version"] = res.stdout.splitlines()[0]
    except Exception as e:
        info["version_error"] = str(e)
    return info


def build_and_test():
    print("[RUNNER] Checking/Building project with CMake (Release)...")
    os.makedirs(BUILD_DIR, exist_ok=True)
    subprocess.run(["cmake", "-S", PROJECT_ROOT, "-B", BUILD_DIR, "-DCMAKE_BUILD_TYPE=Release"], check=True)
    subprocess.run(["cmake", "--build", BUILD_DIR, "--config", "Release", "-j", str(os.cpu_count() or 4)], check=True)

    print("[RUNNER] Executing correctness tests...")
    test_res = subprocess.run([TEST_BIN], capture_output=True, text=True)
    with open(os.path.join(LOGS_DIR, "correctness_test_output.log"), "w") as f:
        f.write(test_res.stdout)
        f.write(test_res.stderr)
    
    if test_res.returncode != 0:
        print(f"[RUNNER] Correctness tests failed with code {test_res.returncode}!")
        print(test_res.stderr)
        sys.exit(1)
    print("[RUNNER] Correctness tests passed successfully.")


def run_benchmark_cmd(args, env, log_file):
    cmd = [BENCHMARK_BIN] + args
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    log_file.write(f"CMD: {' '.join(cmd)}\n")
    if res.stdout:
        log_file.write(res.stdout)
    if res.stderr:
        log_file.write(f"[STDERR] {res.stderr}\n")
    if res.returncode != 0:
        raise RuntimeError(f"Command failed with code {res.returncode}: {' '.join(cmd)}\n{res.stderr}")


def main():
    parser = argparse.ArgumentParser(description="Run CS2 OpenMP Scheduling Experiment Matrix")
    parser.add_argument("--repeats", type=int, default=7, help="Number of measured repetitions (default: 7)")
    parser.add_argument("--warmup", type=int, default=1, help="Number of warmup iterations (default: 1)")
    parser.add_argument("--max-threads", type=int, default=16, help="Cap maximum threads (default: 16)")
    parser.add_argument("--threads", type=str, default="", help="Comma-separated list of threads (e.g. '1,2,4,8,16')")
    parser.add_argument("--seed", type=int, default=42, help="Seed for workload and run order (default: 42)")
    parser.add_argument("--iterations", type=int, default=100000, help="Synthetic loop iterations N (default: 100000)")
    parser.add_argument("--base-work", type=int, default=500, help="Base synthetic work units W (default: 500)")
    parser.add_argument("--mandel-width", type=int, default=1200, help="Mandelbrot width (default: 1200)")
    parser.add_argument("--mandel-height", type=int, default=900, help="Mandelbrot height (default: 900)")
    parser.add_argument("--mandel-max-iter", type=int, default=400, help="Mandelbrot max iter (default: 400)")
    parser.add_argument("--quick", action="store_true", help="Quick mode for verification/smoke testing")
    parser.add_argument("--output-csv", type=str, default=os.path.join(RESULTS_RAW_DIR, "raw_runs.csv"))

    args = parser.parse_args()

    os.makedirs(RESULTS_RAW_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    if args.quick:
        print("[RUNNER] Quick mode enabled: reducing repeats and problem size.")
        args.repeats = 2
        args.warmup = 1
        args.iterations = 20000
        args.base_work = 200
        args.mandel_width = 400
        args.mandel_height = 300
        args.mandel_max_iter = 150

    # Build and test
    build_and_test()

    # Determine thread list
    if args.threads:
        thread_counts = [int(x.strip()) for x in args.threads.split(",") if x.strip()]
    else:
        logical_cpus = os.cpu_count() or 16
        candidates = [1, 2, 4, 8, 16]
        thread_counts = [t for t in candidates if t <= min(logical_cpus, args.max_threads)]
        if logical_cpus not in thread_counts and logical_cpus <= args.max_threads:
            thread_counts.append(logical_cpus)
        thread_counts = sorted(list(set(thread_counts)))

    print(f"[RUNNER] Selected thread counts: {thread_counts}")

    # Environment settings for OpenMP
    env = os.environ.copy()
    env["OMP_DYNAMIC"] = "FALSE"
    env["OMP_PLACES"] = "cores"
    env["OMP_PROC_BIND"] = "close"

    # Capture metadata
    start_time_iso = datetime.now(timezone.utc).isoformat()
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    compiler_info = get_compiler_info()

    meta = {
        "start_time": start_time_iso,
        "platform": platform.platform(),
        "cpu_info": cpu_info,
        "memory_info": mem_info,
        "compiler_info": compiler_info,
        "openmp_env": {
            "OMP_DYNAMIC": env["OMP_DYNAMIC"],
            "OMP_PLACES": env["OMP_PLACES"],
            "OMP_PROC_BIND": env["OMP_PROC_BIND"]
        },
        "python_version": platform.python_version(),
        "benchmark_parameters": {
            "iterations": args.iterations,
            "base_work": args.base_work,
            "mandel_width": args.mandel_width,
            "mandel_height": args.mandel_height,
            "mandel_max_iter": args.mandel_max_iter,
            "repeats": args.repeats,
            "warmup": args.warmup,
            "seed": args.seed,
            "thread_counts": thread_counts
        },
        "cli_command": " ".join(sys.argv)
    }

    # Remove existing raw CSV to start clean
    if os.path.exists(args.output_csv):
        os.remove(args.output_csv)

    workloads = [
        "regular",
        "random_low",
        "random_med",
        "random_high",
        "clustered_high",
        "mandelbrot"
    ]

    sched_configs = [
        ("static_default", 0),
        ("static", 1),
        ("static", 8),
        ("static", 64),
        ("dynamic", 1),
        ("dynamic", 8),
        ("dynamic", 64),
        ("guided", 1),
        ("guided", 8),
        ("guided", 64)
    ]

    log_path = os.path.join(LOGS_DIR, f"experiment_run_{int(time.time())}.log")
    print(f"[RUNNER] Starting experiment matrix. Log file: {log_path}")
    print(f"[RUNNER] Raw output destination: {args.output_csv}")

    rng = random.Random(args.seed)

    total_runs_completed = 0
    start_wall_time = time.time()

    with open(log_path, "w") as log_file:
        # Step 1: Collect Serial Baselines
        print("[RUNNER] === Step 1: Running Serial Baselines ===")
        for wl in workloads:
            print(f"[RUNNER] Serial baseline for workload: {wl}")
            cmd_args = [
                "--mode", "serial",
                "--workload", wl,
                "--iterations", str(args.iterations),
                "--base-work", str(args.base_work),
                "--seed", str(args.seed),
                "--mandel-width", str(args.mandel_width),
                "--mandel-height", str(args.mandel_height),
                "--mandel-max-iter", str(args.mandel_max_iter),
                "--repeats", str(args.repeats),
                "--warmup", str(args.warmup),
                "--output-csv", args.output_csv,
                "--run-id-prefix", f"serial_{wl}"
            ]
            run_benchmark_cmd(cmd_args, env, log_file)
            total_runs_completed += args.repeats

        # Step 2: Collect Dispatch Probes
        print("[RUNNER] === Step 2: Running Low-Work Dispatch Probes ===")
        probe_configs = []
        for policy, chunk in sched_configs:
            for th in thread_counts:
                probe_configs.append((policy, chunk, th))

        for rep in range(args.repeats):
            # Randomize order within each repetition
            shuffled_probes = list(probe_configs)
            rng.shuffle(shuffled_probes)
            for policy, chunk, th in shuffled_probes:
                cmd_args = [
                    "--mode", "probe",
                    "--policy", policy,
                    "--chunk", str(chunk),
                    "--threads", str(th),
                    "--iterations", str(args.iterations),
                    "--repeats", "1",
                    "--warmup", str(args.warmup if rep == 0 else 0),
                    "--output-csv", args.output_csv,
                    "--run-id-prefix", f"probe_{policy}_c{chunk}_t{th}"
                ]
                run_benchmark_cmd(cmd_args, env, log_file)
                total_runs_completed += 1

        # Step 3: Collect Parallel Workloads
        print("[RUNNER] === Step 3: Running Parallel Workloads ===")
        parallel_matrix = []
        for wl in workloads:
            for policy, chunk in sched_configs:
                for th in thread_counts:
                    parallel_matrix.append((wl, policy, chunk, th))

        print(f"[RUNNER] Total parallel configs: {len(parallel_matrix)} across {args.repeats} repetitions")

        for rep in range(args.repeats):
            rep_start = time.time()
            shuffled_matrix = list(parallel_matrix)
            rng.shuffle(shuffled_matrix)
            print(f"[RUNNER] --- Executing Repetition {rep + 1}/{args.repeats} ({len(shuffled_matrix)} items) ---")
            
            for wl, policy, chunk, th in shuffled_matrix:
                cmd_args = [
                    "--mode", "workload",
                    "--workload", wl,
                    "--policy", policy,
                    "--chunk", str(chunk),
                    "--threads", str(th),
                    "--iterations", str(args.iterations),
                    "--base-work", str(args.base_work),
                    "--seed", str(args.seed),
                    "--mandel-width", str(args.mandel_width),
                    "--mandel-height", str(args.mandel_height),
                    "--mandel-max-iter", str(args.mandel_max_iter),
                    "--repeats", "1",
                    "--warmup", str(args.warmup if rep == 0 else 0),
                    "--output-csv", args.output_csv,
                    "--run-id-prefix", f"{wl}_{policy}_c{chunk}_t{th}"
                ]
                run_benchmark_cmd(cmd_args, env, log_file)
                total_runs_completed += 1

            rep_duration = time.time() - rep_start
            print(f"[RUNNER] Completed Repetition {rep + 1}/{args.repeats} in {rep_duration:.2f} s")

    end_wall_time = time.time()
    total_duration = end_wall_time - start_wall_time
    end_time_iso = datetime.now(timezone.utc).isoformat()

    meta["end_time"] = end_time_iso
    meta["total_wall_time_seconds"] = round(total_duration, 2)
    meta["total_records_recorded"] = total_runs_completed

    env_json_path = os.path.join(RESULTS_RAW_DIR, "environment.json")
    with open(env_json_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[RUNNER] Experiment complete in {total_duration:.2f} s.")
    print(f"[RUNNER] Total measurement records: {total_runs_completed}")
    print(f"[RUNNER] Saved raw CSV: {args.output_csv}")
    print(f"[RUNNER] Saved environment metadata: {env_json_path}")


if __name__ == "__main__":
    main()
