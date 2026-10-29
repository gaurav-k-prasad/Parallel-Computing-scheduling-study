#include "benchmark_support.hpp"

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <cstdlib>
#include <cstring>

namespace {

std::string get_iso_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
    
    std::stringstream ss;
    ss << std::put_time(std::gmtime(&in_time_t), "%Y-%m-%dT%H:%M:%S");
    ss << '.' << std::setfill('0') << std::setw(3) << ms.count() << 'Z';
    return ss.str();
}

std::string hex_checksum(uint64_t val) {
    std::stringstream ss;
    ss << "0x" << std::hex << std::setfill('0') << std::setw(16) << val;
    return ss.str();
}

int observe_actual_threads(int requested) {
    int observed = 0;
    omp_set_dynamic(0);
    omp_set_num_threads(requested);
    #pragma omp parallel
    {
        #pragma omp single
        observed = omp_get_num_threads();
    }
    return observed;
}

} // namespace

int main(int argc, char* argv[]) {
    try {
        // Defaults
        std::string mode = "workload"; // "workload", "serial", "probe", "profile"
        std::string workload_str = "regular";
        std::string policy_str = "static_default";
        int chunk_size = 0; // 0 indicates default static
        int requested_threads = 1;
        int repeats = 1;
        int warmup = 0;
        size_t num_iterations = 100000;
        uint32_t base_work = 1000;
        uint64_t seed = 42;
        int mandel_width = 1600;
        int mandel_height = 1200;
        int mandel_max_iter = 500;
        std::string output_csv = "";
        std::string run_id_prefix = "run";

        // Parse CLI arguments
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--mode" && i + 1 < argc) {
                mode = argv[++i];
            } else if (arg == "--workload" && i + 1 < argc) {
                workload_str = argv[++i];
            } else if (arg == "--policy" && i + 1 < argc) {
                policy_str = argv[++i];
            } else if (arg == "--chunk" && i + 1 < argc) {
                chunk_size = std::stoi(argv[++i]);
            } else if (arg == "--threads" && i + 1 < argc) {
                requested_threads = std::stoi(argv[++i]);
            } else if (arg == "--repeats" && i + 1 < argc) {
                repeats = std::stoi(argv[++i]);
            } else if (arg == "--warmup" && i + 1 < argc) {
                warmup = std::stoi(argv[++i]);
            } else if (arg == "--iterations" && i + 1 < argc) {
                num_iterations = static_cast<size_t>(std::stoll(argv[++i]));
            } else if (arg == "--base-work" && i + 1 < argc) {
                base_work = static_cast<uint32_t>(std::stoul(argv[++i]));
            } else if (arg == "--seed" && i + 1 < argc) {
                seed = static_cast<uint64_t>(std::stoull(argv[++i]));
            } else if (arg == "--mandel-width" && i + 1 < argc) {
                mandel_width = std::stoi(argv[++i]);
            } else if (arg == "--mandel-height" && i + 1 < argc) {
                mandel_height = std::stoi(argv[++i]);
            } else if (arg == "--mandel-max-iter" && i + 1 < argc) {
                mandel_max_iter = std::stoi(argv[++i]);
            } else if (arg == "--output-csv" && i + 1 < argc) {
                output_csv = argv[++i];
            } else if (arg == "--run-id-prefix" && i + 1 < argc) {
                run_id_prefix = argv[++i];
            } else if (arg == "--help" || arg == "-h") {
                std::cout << "Usage: " << argv[0] << " [options]\n"
                          << "Options:\n"
                          << "  --mode <workload|serial|probe|profile>\n"
                          << "  --workload <regular|random_low|random_med|random_high|clustered_high|mandelbrot|probe>\n"
                          << "  --policy <static_default|static|dynamic|guided>\n"
                          << "  --chunk <chunk_size> (0 for static_default)\n"
                          << "  --threads <count>\n"
                          << "  --repeats <count>\n"
                          << "  --warmup <count>\n"
                          << "  --iterations <N>\n"
                          << "  --base-work <W>\n"
                          << "  --seed <seed>\n"
                          << "  --mandel-width <w>\n"
                          << "  --mandel-height <h>\n"
                          << "  --mandel-max-iter <iter>\n"
                          << "  --output-csv <path>\n"
                          << "  --run-id-prefix <prefix>\n";
                return 0;
            } else {
                std::cerr << "Unknown argument: " << arg << "\n";
                return 1;
            }
        }

        // Validate basic parameters
        if (requested_threads <= 0) {
            std::cerr << "Error: Thread count must be > 0 (got " << requested_threads << ")\n";
            return 1;
        }
        if (num_iterations == 0) {
            std::cerr << "Error: Iteration count must be > 0\n";
            return 1;
        }
        if (repeats < 0 || warmup < 0) {
            std::cerr << "Error: repeats and warmup must be >= 0\n";
            return 1;
        }

        cs2::SchedPolicy policy = cs2::SchedPolicy::STATIC_DEFAULT;
        if (mode != "serial") {
            policy = cs2::string_to_policy(policy_str);
            if (policy != cs2::SchedPolicy::STATIC_DEFAULT && chunk_size <= 0) {
                std::cerr << "Error: Chunk size must be > 0 for chunked schedule (got " << chunk_size << ")\n";
                return 1;
            }
        }

        int actual_threads = observe_actual_threads(requested_threads);
        std::string chunk_str = (policy == cs2::SchedPolicy::STATIC_DEFAULT) ? "default" : std::to_string(chunk_size);
        std::string compiler_info = "GCC " + std::to_string(__GNUC__) + "." + std::to_string(__GNUC_MINOR__) + "." + std::to_string(__GNUC_PATCHLEVEL__);

        // Handle Workload Profiling Mode (Outputs JSON or key-value stats without timing loops)
        if (mode == "profile") {
            cs2::WorkloadStats stats;
            if (workload_str == "mandelbrot") {
                cs2::MandelbrotConfig m_cfg{mandel_width, mandel_height, mandel_max_iter, -2.0, 0.5, -1.25, 1.25};
                stats = cs2::profile_mandelbrot_workload(m_cfg);
            } else {
                cs2::WorkloadProfile prof = cs2::string_to_profile(workload_str);
                cs2::generate_synthetic_workload(prof, num_iterations, base_work, seed, stats);
            }
            std::cout << "workload_name=" << stats.name << "\n"
                      << "arrangement=" << stats.arrangement << "\n"
                      << "target_cv=" << stats.target_cv << "\n"
                      << "actual_cv=" << stats.actual_cv << "\n"
                      << "total_iterations=" << stats.num_iterations << "\n"
                      << "total_work=" << stats.total_work << "\n"
                      << "mean_cost=" << stats.mean_cost << "\n"
                      << "stddev_cost=" << stats.stddev_cost << "\n"
                      << "min_cost=" << stats.min_cost << "\n"
                      << "max_cost=" << stats.max_cost << "\n"
                      << "max_to_mean=" << stats.max_to_mean << "\n"
                      << "seed=" << stats.seed << "\n";
            return 0;
        }

        // Setup CSV file if requested
        std::ofstream csv_file;
        if (!output_csv.empty()) {
            bool exists = false;
            {
                std::ifstream check(output_csv);
                if (check.good()) exists = true;
            }
            csv_file.open(output_csv, std::ios::out | std::ios::app);
            if (!csv_file.is_open()) {
                std::cerr << "Error: Could not open output CSV: " << output_csv << "\n";
                return 1;
            }
            if (!exists) {
                csv_file << "run_id,measurement_kind,timestamp,workload_name,arrangement,target_cv,actual_cv,"
                         << "total_iterations,total_work_units,scheduling_policy,chunk_size,requested_threads,"
                         << "actual_threads,repetition_index,random_seed,elapsed_ms,checksum,compiler_info,build_type\n";
            }
        }

        // Branch by mode
        if (mode == "probe") {
            // Low-work dispatch probe
            std::vector<uint64_t> out(num_iterations, 0);

            // Warmup
            for (int w = 0; w < warmup; ++w) {
                cs2::run_probe_parallel(num_iterations, out.data(), policy, chunk_size, requested_threads);
            }

            // Measured repeats
            for (int r = 0; r < repeats; ++r) {
                double t0 = omp_get_wtime();
                cs2::run_probe_parallel(num_iterations, out.data(), policy, chunk_size, requested_threads);
                double t1 = omp_get_wtime();
                double elapsed_ms = (t1 - t0) * 1000.0;
                uint64_t cksum = cs2::compute_checksum(out.data(), num_iterations);

                std::string timestamp = get_iso_timestamp();
                std::string run_id = run_id_prefix + "_probe_r" + std::to_string(r);

                if (csv_file.is_open()) {
                    csv_file << run_id << ",dispatch_probe," << timestamp << ",synthetic_probe,dispatch_probe,0.0,0.0,"
                             << num_iterations << "," << num_iterations << "," << cs2::policy_to_string(policy) << ","
                             << chunk_str << "," << requested_threads << "," << actual_threads << ","
                             << r << "," << seed << "," << std::fixed << std::setprecision(6) << elapsed_ms << ","
                             << hex_checksum(cksum) << "," << compiler_info << ",Release\n";
                }
                std::cout << "[PROBE] Rep " << r << ": " << elapsed_ms << " ms, cksum: " << hex_checksum(cksum) << "\n";
            }
        } else if (workload_str == "mandelbrot") {
            // Mandelbrot workload
            cs2::MandelbrotConfig m_cfg{mandel_width, mandel_height, mandel_max_iter, -2.0, 0.5, -1.25, 1.25};
            size_t total_pix = m_cfg.total_pixels();
            cs2::WorkloadStats stats = cs2::profile_mandelbrot_workload(m_cfg);
            std::vector<uint64_t> out(total_pix, 0);

            if (mode == "serial") {
                // Warmup
                for (int w = 0; w < warmup; ++w) {
                    cs2::run_mandelbrot_serial(m_cfg, out.data());
                }
                for (int r = 0; r < repeats; ++r) {
                    double t0 = omp_get_wtime();
                    cs2::run_mandelbrot_serial(m_cfg, out.data());
                    double t1 = omp_get_wtime();
                    double elapsed_ms = (t1 - t0) * 1000.0;
                    uint64_t cksum = cs2::compute_checksum(out.data(), total_pix);

                    std::string timestamp = get_iso_timestamp();
                    std::string run_id = run_id_prefix + "_serial_r" + std::to_string(r);

                    if (csv_file.is_open()) {
                        csv_file << run_id << ",serial," << timestamp << ",mandelbrot," << stats.arrangement << ","
                                 << stats.target_cv << "," << stats.actual_cv << "," << total_pix << ","
                                 << stats.total_work << ",serial,1,1,1," << r << ",0,"
                                 << std::fixed << std::setprecision(6) << elapsed_ms << ","
                                 << hex_checksum(cksum) << "," << compiler_info << ",Release\n";
                    }
                    std::cout << "[MANDEL-SERIAL] Rep " << r << ": " << elapsed_ms << " ms, cksum: " << hex_checksum(cksum) << "\n";
                }
            } else {
                // Parallel Mandelbrot
                for (int w = 0; w < warmup; ++w) {
                    cs2::run_mandelbrot_parallel(m_cfg, out.data(), policy, chunk_size, requested_threads);
                }
                for (int r = 0; r < repeats; ++r) {
                    double t0 = omp_get_wtime();
                    cs2::run_mandelbrot_parallel(m_cfg, out.data(), policy, chunk_size, requested_threads);
                    double t1 = omp_get_wtime();
                    double elapsed_ms = (t1 - t0) * 1000.0;
                    uint64_t cksum = cs2::compute_checksum(out.data(), total_pix);

                    std::string timestamp = get_iso_timestamp();
                    std::string run_id = run_id_prefix + "_workload_r" + std::to_string(r);

                    if (csv_file.is_open()) {
                        csv_file << run_id << ",workload," << timestamp << ",mandelbrot," << stats.arrangement << ","
                                 << stats.target_cv << "," << stats.actual_cv << "," << total_pix << ","
                                 << stats.total_work << "," << cs2::policy_to_string(policy) << ","
                                 << chunk_str << "," << requested_threads << "," << actual_threads << ","
                                 << r << ",0,"
                                 << std::fixed << std::setprecision(6) << elapsed_ms << ","
                                 << hex_checksum(cksum) << "," << compiler_info << ",Release\n";
                    }
                    std::cout << "[MANDEL-PARALLEL] Rep " << r << ": " << elapsed_ms << " ms, cksum: " << hex_checksum(cksum) << "\n";
                }
            }
        } else {
            // Synthetic Workload
            cs2::WorkloadProfile prof = cs2::string_to_profile(workload_str);
            cs2::WorkloadStats stats;
            std::vector<uint32_t> W = cs2::generate_synthetic_workload(prof, num_iterations, base_work, seed, stats);
            std::vector<uint64_t> out(num_iterations, 0);

            if (mode == "serial") {
                // Genuine serial execution
                for (int w = 0; w < warmup; ++w) {
                    cs2::run_synthetic_serial(W.data(), num_iterations, out.data());
                }
                for (int r = 0; r < repeats; ++r) {
                    double t0 = omp_get_wtime();
                    cs2::run_synthetic_serial(W.data(), num_iterations, out.data());
                    double t1 = omp_get_wtime();
                    double elapsed_ms = (t1 - t0) * 1000.0;
                    uint64_t cksum = cs2::compute_checksum(out.data(), num_iterations);

                    std::string timestamp = get_iso_timestamp();
                    std::string run_id = run_id_prefix + "_serial_r" + std::to_string(r);

                    if (csv_file.is_open()) {
                        csv_file << run_id << ",serial," << timestamp << "," << stats.name << "," << stats.arrangement << ","
                                 << stats.target_cv << "," << stats.actual_cv << "," << num_iterations << ","
                                 << stats.total_work << ",serial,1,1,1," << r << "," << seed << ","
                                 << std::fixed << std::setprecision(6) << elapsed_ms << ","
                                 << hex_checksum(cksum) << "," << compiler_info << ",Release\n";
                    }
                    std::cout << "[SYNTH-SERIAL] " << stats.name << " Rep " << r << ": " << elapsed_ms << " ms, cksum: " << hex_checksum(cksum) << "\n";
                }
            } else {
                // OpenMP parallel execution
                for (int w = 0; w < warmup; ++w) {
                    cs2::run_synthetic_parallel(W.data(), num_iterations, out.data(), policy, chunk_size, requested_threads);
                }
                for (int r = 0; r < repeats; ++r) {
                    double t0 = omp_get_wtime();
                    cs2::run_synthetic_parallel(W.data(), num_iterations, out.data(), policy, chunk_size, requested_threads);
                    double t1 = omp_get_wtime();
                    double elapsed_ms = (t1 - t0) * 1000.0;
                    uint64_t cksum = cs2::compute_checksum(out.data(), num_iterations);

                    std::string timestamp = get_iso_timestamp();
                    std::string run_id = run_id_prefix + "_workload_r" + std::to_string(r);

                    if (csv_file.is_open()) {
                        csv_file << run_id << ",workload," << timestamp << "," << stats.name << "," << stats.arrangement << ","
                                 << stats.target_cv << "," << stats.actual_cv << "," << num_iterations << ","
                                 << stats.total_work << "," << cs2::policy_to_string(policy) << ","
                                 << chunk_str << "," << requested_threads << "," << actual_threads << ","
                                 << r << "," << seed << ","
                                 << std::fixed << std::setprecision(6) << elapsed_ms << ","
                                 << hex_checksum(cksum) << "," << compiler_info << ",Release\n";
                    }
                    std::cout << "[SYNTH-PARALLEL] " << stats.name << " " << cs2::policy_to_string(policy)
                              << " c=" << chunk_str << " th=" << requested_threads
                              << " Rep " << r << ": " << elapsed_ms << " ms, cksum: " << hex_checksum(cksum) << "\n";
                }
            }
        }

        if (csv_file.is_open()) {
            csv_file.close();
        }

    } catch (const std::exception& e) {
        std::cerr << "Fatal Exception: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
