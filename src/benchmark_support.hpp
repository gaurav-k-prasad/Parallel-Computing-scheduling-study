#pragma once

#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <numeric>
#include <algorithm>
#include <random>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <omp.h>

namespace cs2 {

enum class WorkloadProfile {
    REGULAR,
    RANDOM_LOW,
    RANDOM_MED,
    RANDOM_HIGH,
    CLUSTERED_HIGH
};

inline std::string profile_to_string(WorkloadProfile profile) {
    switch (profile) {
        case WorkloadProfile::REGULAR: return "regular";
        case WorkloadProfile::RANDOM_LOW: return "random_low";
        case WorkloadProfile::RANDOM_MED: return "random_med";
        case WorkloadProfile::RANDOM_HIGH: return "random_high";
        case WorkloadProfile::CLUSTERED_HIGH: return "clustered_high";
    }
    return "unknown";
}

inline WorkloadProfile string_to_profile(const std::string& str) {
    if (str == "regular") return WorkloadProfile::REGULAR;
    if (str == "random_low") return WorkloadProfile::RANDOM_LOW;
    if (str == "random_med") return WorkloadProfile::RANDOM_MED;
    if (str == "random_high") return WorkloadProfile::RANDOM_HIGH;
    if (str == "clustered_high") return WorkloadProfile::CLUSTERED_HIGH;
    throw std::invalid_argument("Unknown workload profile: " + str);
}

enum class SchedPolicy {
    STATIC_DEFAULT,
    STATIC_CHUNK,
    DYNAMIC_CHUNK,
    GUIDED_CHUNK
};

inline std::string policy_to_string(SchedPolicy policy) {
    switch (policy) {
        case SchedPolicy::STATIC_DEFAULT: return "static_default";
        case SchedPolicy::STATIC_CHUNK: return "static";
        case SchedPolicy::DYNAMIC_CHUNK: return "dynamic";
        case SchedPolicy::GUIDED_CHUNK: return "guided";
    }
    return "unknown";
}

inline SchedPolicy string_to_policy(const std::string& str) {
    if (str == "static_default" || str == "static-default") return SchedPolicy::STATIC_DEFAULT;
    if (str == "static") return SchedPolicy::STATIC_CHUNK;
    if (str == "dynamic") return SchedPolicy::DYNAMIC_CHUNK;
    if (str == "guided") return SchedPolicy::GUIDED_CHUNK;
    throw std::invalid_argument("Unknown scheduling policy: " + str);
}

struct WorkloadStats {
    std::string name;
    std::string arrangement; // "uniform", "randomized", "clustered"
    double target_cv = 0.0;
    double actual_cv = 0.0;
    double mean_cost = 0.0;
    double stddev_cost = 0.0;
    uint32_t min_cost = 0;
    uint32_t max_cost = 0;
    double max_to_mean = 0.0;
    uint64_t total_work = 0;
    size_t num_iterations = 0;
    uint64_t seed = 0;
};

// Compute statistical summary of costs
inline WorkloadStats compute_cost_stats(const std::vector<uint32_t>& costs, 
                                       const std::string& name,
                                       const std::string& arrangement,
                                       double target_cv,
                                       uint64_t seed) {
    WorkloadStats stats;
    stats.name = name;
    stats.arrangement = arrangement;
    stats.target_cv = target_cv;
    stats.seed = seed;
    stats.num_iterations = costs.size();

    if (costs.empty()) {
        return stats;
    }

    uint64_t sum = 0;
    uint32_t min_val = costs[0];
    uint32_t max_val = costs[0];

    for (uint32_t c : costs) {
        sum += c;
        if (c < min_val) min_val = c;
        if (c > max_val) max_val = c;
    }

    stats.total_work = sum;
    stats.min_cost = min_val;
    stats.max_cost = max_val;
    stats.mean_cost = static_cast<double>(sum) / costs.size();
    stats.max_to_mean = (stats.mean_cost > 0.0) ? (static_cast<double>(max_val) / stats.mean_cost) : 0.0;

    double sq_diff_sum = 0.0;
    for (uint32_t c : costs) {
        double diff = static_cast<double>(c) - stats.mean_cost;
        sq_diff_sum += diff * diff;
    }

    stats.stddev_cost = std::sqrt(sq_diff_sum / costs.size());
    stats.actual_cv = (stats.mean_cost > 0.0) ? (stats.stddev_cost / stats.mean_cost) : 0.0;

    return stats;
}

// Generate synthetic workload costs according to specification
inline std::vector<uint32_t> generate_synthetic_workload(WorkloadProfile profile,
                                                         size_t N,
                                                         uint32_t base_work,
                                                         uint64_t seed,
                                                         WorkloadStats& stats) {
    if (N == 0) {
        throw std::invalid_argument("Iteration count N must be > 0");
    }
    if (base_work == 0) {
        throw std::invalid_argument("Base work must be > 0");
    }

    std::vector<uint32_t> costs(N, base_work);
    uint64_t total_budget = static_cast<uint64_t>(N) * base_work;

    if (profile == WorkloadProfile::REGULAR) {
        stats = compute_cost_stats(costs, profile_to_string(profile), "uniform", 0.0, seed);
        return costs;
    }

    double target_cv = 0.0;
    if (profile == WorkloadProfile::RANDOM_LOW) {
        target_cv = 0.25;
    } else if (profile == WorkloadProfile::RANDOM_MED) {
        target_cv = 0.50;
    } else if (profile == WorkloadProfile::RANDOM_HIGH || profile == WorkloadProfile::CLUSTERED_HIGH) {
        target_cv = 1.00;
    }

    // Gamma distribution: shape k = 1 / (CV^2), scale theta = 1.0
    double k = 1.0 / (target_cv * target_cv);
    std::mt19937_64 rng(seed);
    std::gamma_distribution<double> dist(k, 1.0);

    std::vector<double> raw(N);
    double raw_sum = 0.0;
    for (size_t i = 0; i < N; ++i) {
        raw[i] = dist(rng);
        raw_sum += raw[i];
    }

    // Scale to total_budget and enforce minimum 1
    std::vector<double> scaled(N);
    std::vector<uint32_t> int_costs(N);
    uint64_t current_int_sum = 0;

    struct RemainderItem {
        double rem;
        size_t index;
    };
    std::vector<RemainderItem> remainders(N);

    for (size_t i = 0; i < N; ++i) {
        scaled[i] = (raw[i] / raw_sum) * static_cast<double>(total_budget);
        uint32_t floor_val = static_cast<uint32_t>(scaled[i]);
        if (floor_val < 1) floor_val = 1;
        int_costs[i] = floor_val;
        current_int_sum += floor_val;
        remainders[i] = {scaled[i] - floor_val, i};
    }

    // Deterministically distribute remainder so sum exactly equals total_budget
    if (current_int_sum < total_budget) {
        uint64_t deficit = total_budget - current_int_sum;
        // Sort remainders descending, breaking ties with index
        std::sort(remainders.begin(), remainders.end(), [](const RemainderItem& a, const RemainderItem& b) {
            if (std::abs(a.rem - b.rem) > 1e-9) return a.rem > b.rem;
            return a.index < b.index;
        });
        for (size_t i = 0; i < deficit && i < N; ++i) {
            int_costs[remainders[i].index] += 1;
        }
    } else if (current_int_sum > total_budget) {
        uint64_t surplus = current_int_sum - total_budget;
        // Subtract from items where int_costs > 1, sorted by smallest fractional remainder
        std::sort(remainders.begin(), remainders.end(), [](const RemainderItem& a, const RemainderItem& b) {
            if (std::abs(a.rem - b.rem) > 1e-9) return a.rem < b.rem;
            return a.index < b.index;
        });
        size_t idx = 0;
        while (surplus > 0 && idx < N) {
            size_t target_idx = remainders[idx].index;
            if (int_costs[target_idx] > 1) {
                int_costs[target_idx] -= 1;
                --surplus;
            }
            ++idx;
        }
    }

    if (profile == WorkloadProfile::CLUSTERED_HIGH) {
        // Rearrange the generated costs so the most expensive iterations are clustered
        // in a contiguous central block [N/4, 3N/4], preserving exact multiset and histogram
        std::vector<uint32_t> sorted_costs = int_costs;
        std::sort(sorted_costs.begin(), sorted_costs.end()); // ascending

        std::vector<uint32_t> clustered(N);
        size_t cluster_start = N / 4;
        size_t cluster_end = cluster_start + (N / 2); // 50% contiguous region in middle

        // Fill middle [cluster_start, cluster_end) with highest costs
        size_t high_idx = N / 2; // highest N/2 items are from sorted_costs[high_idx ... N-1]
        for (size_t i = cluster_start; i < cluster_end; ++i) {
            clustered[i] = sorted_costs[high_idx++];
        }

        // Fill remaining outer sections [0, cluster_start) and [cluster_end, N) with lower costs
        size_t low_idx = 0;
        for (size_t i = 0; i < cluster_start; ++i) {
            clustered[i] = sorted_costs[low_idx++];
        }
        for (size_t i = cluster_end; i < N; ++i) {
            clustered[i] = sorted_costs[low_idx++];
        }

        costs = clustered;
        stats = compute_cost_stats(costs, profile_to_string(profile), "clustered", target_cv, seed);
        return costs;
    }

    costs = int_costs;
    stats = compute_cost_stats(costs, profile_to_string(profile), "randomized", target_cv, seed);
    return costs;
}

// 64-bit FNV-1a checksum calculation
inline uint64_t compute_checksum(const uint64_t* data, size_t N) {
    uint64_t hash = 0xcbf29ce484222325ULL;
    for (size_t i = 0; i < N; ++i) {
        hash ^= data[i];
        hash *= 0x100000001b3ULL;
    }
    return hash;
}

// Deterministic synthetic kernel for iteration i given cost W_i
inline uint64_t execute_synthetic_kernel(size_t i, uint32_t cost) {
    uint64_t state = static_cast<uint64_t>(i) ^ 0x9e3779b97f4a7c15ULL;
    for (uint32_t step = 0; step < cost; ++step) {
        state ^= (state >> 30);
        state *= 0xbf58476d1ce4e5b9ULL;
        state ^= (state >> 27);
        state *= 0x94d049bb133111ebULL;
        state ^= (state >> 31);
        state += step;
    }
    return state;
}

// Serial synthetic workload implementation
inline void run_synthetic_serial(const uint32_t* W, size_t N, uint64_t* out) {
    for (size_t i = 0; i < N; ++i) {
        out[i] = execute_synthetic_kernel(i, W[i]);
    }
}

// OpenMP parallel synthetic workload implementation
inline void run_synthetic_parallel(const uint32_t* W, size_t N, uint64_t* out,
                                  SchedPolicy policy, int chunk_size, int num_threads) {
    omp_set_dynamic(0);
    omp_set_num_threads(num_threads);

    if (policy == SchedPolicy::STATIC_DEFAULT) {
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < N; ++i) {
            out[i] = execute_synthetic_kernel(i, W[i]);
        }
    } else {
        omp_sched_t omp_sched = omp_sched_static;
        if (policy == SchedPolicy::STATIC_CHUNK) {
            omp_sched = omp_sched_static;
        } else if (policy == SchedPolicy::DYNAMIC_CHUNK) {
            omp_sched = omp_sched_dynamic;
        } else if (policy == SchedPolicy::GUIDED_CHUNK) {
            omp_sched = omp_sched_guided;
        }
        omp_set_schedule(omp_sched, chunk_size);

        #pragma omp parallel for schedule(runtime)
        for (size_t i = 0; i < N; ++i) {
            out[i] = execute_synthetic_kernel(i, W[i]);
        }
    }
}

// Low-work dispatch probe loop (minimal arithmetic per iteration to isolate dispatch overhead)
inline uint64_t execute_probe_kernel(size_t i) {
    return (static_cast<uint64_t>(i) * 3141592653589793238ULL) ^ 0x5a5a5a5a5a5a5a5aULL;
}

inline void run_probe_serial(size_t N, uint64_t* out) {
    for (size_t i = 0; i < N; ++i) {
        out[i] = execute_probe_kernel(i);
    }
}

inline void run_probe_parallel(size_t N, uint64_t* out,
                               SchedPolicy policy, int chunk_size, int num_threads) {
    omp_set_dynamic(0);
    omp_set_num_threads(num_threads);

    if (policy == SchedPolicy::STATIC_DEFAULT) {
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < N; ++i) {
            out[i] = execute_probe_kernel(i);
        }
    } else {
        omp_sched_t omp_sched = omp_sched_static;
        if (policy == SchedPolicy::STATIC_CHUNK) {
            omp_sched = omp_sched_static;
        } else if (policy == SchedPolicy::DYNAMIC_CHUNK) {
            omp_sched = omp_sched_dynamic;
        } else if (policy == SchedPolicy::GUIDED_CHUNK) {
            omp_sched = omp_sched_guided;
        }
        omp_set_schedule(omp_sched, chunk_size);

        #pragma omp parallel for schedule(runtime)
        for (size_t i = 0; i < N; ++i) {
            out[i] = execute_probe_kernel(i);
        }
    }
}

// Mandelbrot benchmark configuration and implementation
struct MandelbrotConfig {
    int width = 1600;
    int height = 1200;
    int max_iter = 500;
    double x_min = -2.0;
    double x_max = 0.5;
    double y_min = -1.25;
    double y_max = 1.25;

    size_t total_pixels() const {
        return static_cast<size_t>(width) * static_cast<size_t>(height);
    }
};

inline uint32_t compute_mandelbrot_pixel(size_t idx, const MandelbrotConfig& config) {
    int r = static_cast<int>(idx / config.width);
    int c = static_cast<int>(idx % config.width);

    double x0 = config.x_min + (static_cast<double>(c) / static_cast<double>(config.width)) * (config.x_max - config.x_min);
    double y0 = config.y_min + (static_cast<double>(r) / static_cast<double>(config.height)) * (config.y_max - config.y_min);

    double x = 0.0;
    double y = 0.0;
    double x2 = 0.0;
    double y2 = 0.0;
    int iter = 0;

    while (x2 + y2 <= 4.0 && iter < config.max_iter) {
        y = 2.0 * x * y + y0;
        x = x2 - y2 + x0;
        x2 = x * x;
        y2 = y * y;
        ++iter;
    }

    return static_cast<uint32_t>(iter);
}

inline void run_mandelbrot_serial(const MandelbrotConfig& config, uint64_t* out) {
    size_t N = config.total_pixels();
    for (size_t i = 0; i < N; ++i) {
        out[i] = compute_mandelbrot_pixel(i, config);
    }
}

inline void run_mandelbrot_parallel(const MandelbrotConfig& config, uint64_t* out,
                                    SchedPolicy policy, int chunk_size, int num_threads) {
    size_t N = config.total_pixels();
    omp_set_dynamic(0);
    omp_set_num_threads(num_threads);

    if (policy == SchedPolicy::STATIC_DEFAULT) {
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < N; ++i) {
            out[i] = compute_mandelbrot_pixel(i, config);
        }
    } else {
        omp_sched_t omp_sched = omp_sched_static;
        if (policy == SchedPolicy::STATIC_CHUNK) {
            omp_sched = omp_sched_static;
        } else if (policy == SchedPolicy::DYNAMIC_CHUNK) {
            omp_sched = omp_sched_dynamic;
        } else if (policy == SchedPolicy::GUIDED_CHUNK) {
            omp_sched = omp_sched_guided;
        }
        omp_set_schedule(omp_sched, chunk_size);

        #pragma omp parallel for schedule(runtime)
        for (size_t i = 0; i < N; ++i) {
            out[i] = compute_mandelbrot_pixel(i, config);
        }
    }
}

// Profile Mandelbrot escape iteration distribution
inline WorkloadStats profile_mandelbrot_workload(const MandelbrotConfig& config) {
    size_t N = config.total_pixels();
    std::vector<uint32_t> escape_counts(N);
    for (size_t i = 0; i < N; ++i) {
        escape_counts[i] = compute_mandelbrot_pixel(i, config);
    }
    return compute_cost_stats(escape_counts, "mandelbrot", "fractal_geometry", -1.0, 0);
}

} // namespace cs2
