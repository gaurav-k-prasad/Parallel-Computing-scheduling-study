#include "../src/benchmark_support.hpp"

#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include <cmath>
#include <algorithm>

namespace {

int g_tests_passed = 0;
int g_tests_failed = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (" << __FILE__ << ":" << __LINE__ << ")\n"; \
            g_tests_failed++; \
            return; \
        } \
    } while (0)

#define RUN_TEST(fn) \
    do { \
        std::cout << "[RUNNING] " << #fn << "..." << std::endl; \
        int prev_failed = g_tests_failed; \
        fn(); \
        if (g_tests_failed == prev_failed) { \
            std::cout << "[PASSED]  " << #fn << std::endl; \
            g_tests_passed++; \
        } else { \
            std::cout << "[FAILED]  " << #fn << std::endl; \
        } \
    } while (0)

} // namespace

void test_workload_determinism() {
    size_t N = 10000;
    uint32_t base_work = 500;
    uint64_t seed = 12345;

    cs2::WorkloadStats s1, s2, s3;
    auto w1 = cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed, s1);
    auto w2 = cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed, s2);
    auto w3 = cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed + 1, s3);

    TEST_ASSERT(w1.size() == N, "Size matches N");
    TEST_ASSERT(w1 == w2, "Identical seed produces identical costs");
    TEST_ASSERT(s1.total_work == s2.total_work, "Total work is identical for identical seed");
    TEST_ASSERT(w1 != w3, "Different seed produces different costs");
}

void test_regular_workload_cv() {
    size_t N = 10000;
    uint32_t base_work = 500;
    uint64_t seed = 42;

    cs2::WorkloadStats stats;
    auto w = cs2::generate_synthetic_workload(cs2::WorkloadProfile::REGULAR, N, base_work, seed, stats);

    TEST_ASSERT(stats.actual_cv == 0.0, "Regular workload CV must be 0.0");
    TEST_ASSERT(stats.min_cost == base_work, "Min cost equals base_work");
    TEST_ASSERT(stats.max_cost == base_work, "Max cost equals base_work");
    TEST_ASSERT(stats.mean_cost == static_cast<double>(base_work), "Mean cost equals base_work");
    TEST_ASSERT(stats.total_work == static_cast<uint64_t>(N) * base_work, "Total budget preserved");
}

void test_irregularity_scaling() {
    size_t N = 20000;
    uint32_t base_work = 1000;
    uint64_t seed = 999;

    cs2::WorkloadStats s_low, s_med, s_high;
    cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_LOW, N, base_work, seed, s_low);
    cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_MED, N, base_work, seed, s_med);
    cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed, s_high);

    TEST_ASSERT(s_low.actual_cv > 0.15 && s_low.actual_cv < 0.35, "Low CV matches target 0.25");
    TEST_ASSERT(s_med.actual_cv > 0.40 && s_med.actual_cv < 0.60, "Med CV matches target 0.50");
    TEST_ASSERT(s_high.actual_cv > 0.85 && s_high.actual_cv < 1.15, "High CV matches target 1.00");

    TEST_ASSERT(s_low.actual_cv < s_med.actual_cv, "CV_low < CV_med");
    TEST_ASSERT(s_med.actual_cv < s_high.actual_cv, "CV_med < CV_high");

    TEST_ASSERT(s_low.total_work == static_cast<uint64_t>(N) * base_work, "Low budget exact");
    TEST_ASSERT(s_med.total_work == static_cast<uint64_t>(N) * base_work, "Med budget exact");
    TEST_ASSERT(s_high.total_work == static_cast<uint64_t>(N) * base_work, "High budget exact");
}

void test_clustered_vs_random_histogram_conservation() {
    size_t N = 20000;
    uint32_t base_work = 1000;
    uint64_t seed = 4242;

    cs2::WorkloadStats s_rand, s_clust;
    auto w_rand = cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed, s_rand);
    auto w_clust = cs2::generate_synthetic_workload(cs2::WorkloadProfile::CLUSTERED_HIGH, N, base_work, seed, s_clust);

    TEST_ASSERT(s_rand.total_work == s_clust.total_work, "Total work is strictly identical");
    TEST_ASSERT(std::abs(s_rand.actual_cv - s_clust.actual_cv) < 1e-9, "Actual CV is strictly identical");
    TEST_ASSERT(s_rand.min_cost == s_clust.min_cost, "Min cost is strictly identical");
    TEST_ASSERT(s_rand.max_cost == s_clust.max_cost, "Max cost is strictly identical");
    TEST_ASSERT(std::abs(s_rand.mean_cost - s_clust.mean_cost) < 1e-9, "Mean cost is strictly identical");
    TEST_ASSERT(std::abs(s_rand.stddev_cost - s_clust.stddev_cost) < 1e-9, "Stddev cost is strictly identical");

    // Verify exact multiset/histogram equality via sorting
    auto sorted_rand = w_rand;
    auto sorted_clust = w_clust;
    std::sort(sorted_rand.begin(), sorted_rand.end());
    std::sort(sorted_clust.begin(), sorted_clust.end());
    TEST_ASSERT(sorted_rand == sorted_clust, "Work-cost multiset/histogram is exactly identical");

    // Verify spatial clustering: the central half [N/4, 3N/4) in clustered must contain more work than randomized
    size_t start = N / 4;
    size_t end = start + N / 2;
    uint64_t mid_sum_rand = 0;
    uint64_t mid_sum_clust = 0;
    for (size_t i = start; i < end; ++i) {
        mid_sum_rand += w_rand[i];
        mid_sum_clust += w_clust[i];
    }
    TEST_ASSERT(mid_sum_clust > mid_sum_rand, "Clustered profile concentrates high-cost work in the central region");
}

void test_synthetic_parallel_checksum_agreement() {
    size_t N = 10000;
    uint32_t base_work = 200;
    uint64_t seed = 777;

    cs2::WorkloadStats stats;
    auto W = cs2::generate_synthetic_workload(cs2::WorkloadProfile::RANDOM_HIGH, N, base_work, seed, stats);

    std::vector<uint64_t> serial_out(N, 0);
    cs2::run_synthetic_serial(W.data(), N, serial_out.data());
    uint64_t expected_cksum = cs2::compute_checksum(serial_out.data(), N);

    struct SchedConfig {
        cs2::SchedPolicy policy;
        int chunk;
        const char* name;
    };

    std::vector<SchedConfig> configs = {
        {cs2::SchedPolicy::STATIC_DEFAULT, 0, "static_default"},
        {cs2::SchedPolicy::STATIC_CHUNK, 1, "static_c1"},
        {cs2::SchedPolicy::STATIC_CHUNK, 8, "static_c8"},
        {cs2::SchedPolicy::STATIC_CHUNK, 64, "static_c64"},
        {cs2::SchedPolicy::DYNAMIC_CHUNK, 1, "dynamic_c1"},
        {cs2::SchedPolicy::DYNAMIC_CHUNK, 8, "dynamic_c8"},
        {cs2::SchedPolicy::DYNAMIC_CHUNK, 64, "dynamic_c64"},
        {cs2::SchedPolicy::GUIDED_CHUNK, 1, "guided_c1"},
        {cs2::SchedPolicy::GUIDED_CHUNK, 8, "guided_c8"},
        {cs2::SchedPolicy::GUIDED_CHUNK, 64, "guided_c64"}
    };

    std::vector<int> thread_counts = {1, 2, 4, 8};

    for (int threads : thread_counts) {
        for (const auto& cfg : configs) {
            std::vector<uint64_t> par_out(N, 0);
            cs2::run_synthetic_parallel(W.data(), N, par_out.data(), cfg.policy, cfg.chunk, threads);
            uint64_t par_cksum = cs2::compute_checksum(par_out.data(), N);
            std::string desc = std::string(cfg.name) + " with " + std::to_string(threads) + " threads matches serial checksum";
            TEST_ASSERT(par_cksum == expected_cksum, desc);
        }
    }
}

void test_mandelbrot_parallel_checksum_agreement() {
    cs2::MandelbrotConfig m_cfg{200, 150, 100, -2.0, 0.5, -1.25, 1.25};
    size_t N = m_cfg.total_pixels();

    std::vector<uint64_t> serial_out(N, 0);
    cs2::run_mandelbrot_serial(m_cfg, serial_out.data());
    uint64_t expected_cksum = cs2::compute_checksum(serial_out.data(), N);

    std::vector<int> chunks = {1, 8, 64};
    std::vector<int> thread_counts = {1, 2, 4};

    for (int th : thread_counts) {
        // static default
        std::vector<uint64_t> out_sd(N, 0);
        cs2::run_mandelbrot_parallel(m_cfg, out_sd.data(), cs2::SchedPolicy::STATIC_DEFAULT, 0, th);
        TEST_ASSERT(cs2::compute_checksum(out_sd.data(), N) == expected_cksum, "Mandelbrot static default matches serial");

        for (int c : chunks) {
            std::vector<uint64_t> out_s(N, 0);
            cs2::run_mandelbrot_parallel(m_cfg, out_s.data(), cs2::SchedPolicy::STATIC_CHUNK, c, th);
            TEST_ASSERT(cs2::compute_checksum(out_s.data(), N) == expected_cksum, "Mandelbrot static chunk matches serial");

            std::vector<uint64_t> out_d(N, 0);
            cs2::run_mandelbrot_parallel(m_cfg, out_d.data(), cs2::SchedPolicy::DYNAMIC_CHUNK, c, th);
            TEST_ASSERT(cs2::compute_checksum(out_d.data(), N) == expected_cksum, "Mandelbrot dynamic chunk matches serial");

            std::vector<uint64_t> out_g(N, 0);
            cs2::run_mandelbrot_parallel(m_cfg, out_g.data(), cs2::SchedPolicy::GUIDED_CHUNK, c, th);
            TEST_ASSERT(cs2::compute_checksum(out_g.data(), N) == expected_cksum, "Mandelbrot guided chunk matches serial");
        }
    }
}

void test_dispatch_probe_agreement() {
    size_t N = 5000;
    std::vector<uint64_t> serial_out(N, 0);
    cs2::run_probe_serial(N, serial_out.data());
    uint64_t expected_cksum = cs2::compute_checksum(serial_out.data(), N);

    std::vector<uint64_t> par_out(N, 0);
    cs2::run_probe_parallel(N, par_out.data(), cs2::SchedPolicy::STATIC_DEFAULT, 0, 4);
    TEST_ASSERT(cs2::compute_checksum(par_out.data(), N) == expected_cksum, "Probe static default matches serial");

    cs2::run_probe_parallel(N, par_out.data(), cs2::SchedPolicy::DYNAMIC_CHUNK, 8, 4);
    TEST_ASSERT(cs2::compute_checksum(par_out.data(), N) == expected_cksum, "Probe dynamic chunk matches serial");
}

void test_thread_count_observation() {
    std::vector<int> test_threads = {1, 2, 4, 8};
    for (int t : test_threads) {
        omp_set_dynamic(0);
        omp_set_num_threads(t);
        int observed = 0;
        #pragma omp parallel
        {
            #pragma omp single
            observed = omp_get_num_threads();
        }
        TEST_ASSERT(observed == t, "Observed thread count matches requested thread count");
    }
}

void test_invalid_parameters_handling() {
    cs2::WorkloadStats stats;
    bool caught_zero_n = false;
    try {
        cs2::generate_synthetic_workload(cs2::WorkloadProfile::REGULAR, 0, 100, 1, stats);
    } catch (const std::invalid_argument&) {
        caught_zero_n = true;
    }
    TEST_ASSERT(caught_zero_n, "Zero iteration count throws std::invalid_argument");

    bool caught_zero_work = false;
    try {
        cs2::generate_synthetic_workload(cs2::WorkloadProfile::REGULAR, 100, 0, 1, stats);
    } catch (const std::invalid_argument&) {
        caught_zero_work = true;
    }
    TEST_ASSERT(caught_zero_work, "Zero base work throws std::invalid_argument");

    bool caught_unknown_profile = false;
    try {
        cs2::string_to_profile("invalid_profile_foo");
    } catch (const std::invalid_argument&) {
        caught_unknown_profile = true;
    }
    TEST_ASSERT(caught_unknown_profile, "Unknown profile string throws std::invalid_argument");

    bool caught_unknown_policy = false;
    try {
        cs2::string_to_policy("invalid_policy_bar");
    } catch (const std::invalid_argument&) {
        caught_unknown_policy = true;
    }
    TEST_ASSERT(caught_unknown_policy, "Unknown policy string throws std::invalid_argument");
}

int main() {
    std::cout << "========================================\n"
              << "CS2 Scheduling Study: Correctness Tests\n"
              << "========================================\n";

    RUN_TEST(test_workload_determinism);
    RUN_TEST(test_regular_workload_cv);
    RUN_TEST(test_irregularity_scaling);
    RUN_TEST(test_clustered_vs_random_histogram_conservation);
    RUN_TEST(test_synthetic_parallel_checksum_agreement);
    RUN_TEST(test_mandelbrot_parallel_checksum_agreement);
    RUN_TEST(test_dispatch_probe_agreement);
    RUN_TEST(test_thread_count_observation);
    RUN_TEST(test_invalid_parameters_handling);

    std::cout << "========================================\n"
              << "Test Summary: " << g_tests_passed << " passed, " << g_tests_failed << " failed.\n"
              << "========================================\n";

    return (g_tests_failed == 0) ? 0 : 1;
}
