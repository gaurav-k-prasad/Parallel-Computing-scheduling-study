cmake_minimum_required(VERSION 3.16)
project(CS2SchedulingStudy VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable compiler warnings
if(MSVC)
    add_compile_options(/W4 /O2)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -O3)
endif()

# Find OpenMP
find_package(OpenMP REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src)

# Benchmark executable
add_executable(benchmark src/benchmark.cpp)
target_link_libraries(benchmark PRIVATE OpenMP::OpenMP_CXX)

# Correctness tests executable
add_executable(correctness_tests tests/correctness_tests.cpp)
target_link_libraries(correctness_tests PRIVATE OpenMP::OpenMP_CXX)

# Enable CTest
enable_testing()
add_test(NAME CorrectnessTests COMMAND correctness_tests)
