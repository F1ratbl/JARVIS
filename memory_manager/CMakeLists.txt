# ═══════════════════════════════════════════
# 🤖 JARVIS — C++ Bellek Yönetim Modülü
# CMake derleme yapılandırması
#
# Gereksinimler:
#   - CMake >= 3.14
#   - C++17 derleyici
#   - pybind11 (pip install pybind11)
# ═══════════════════════════════════════════

cmake_minimum_required(VERSION 3.14)
project(jarvis_memory_manager LANGUAGES CXX)

# C++17 standardı
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ── pybind11'i bul (pip ile kurulmuş olmalı) ──
# pybind11'in CMake dizinini Python'dan al
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE PYBIND11_RESULT
)

# Eğer Python3_EXECUTABLE henüz set edilmediyse, find_package dene
if(NOT PYBIND11_RESULT EQUAL 0)
    find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
    execute_process(
        COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
        OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE PYBIND11_RESULT
    )
endif()

if(PYBIND11_RESULT EQUAL 0 AND EXISTS "${PYBIND11_CMAKE_DIR}")
    # pip ile kurulmuş pybind11
    set(pybind11_DIR "${PYBIND11_CMAKE_DIR}")
    find_package(pybind11 REQUIRED CONFIG)
    message(STATUS "✅ pybind11 bulundu: ${PYBIND11_CMAKE_DIR}")
else()
    # Fallback: sistem genelinde kurulmuş pybind11
    find_package(pybind11 REQUIRED)
    message(STATUS "✅ pybind11 bulundu (sistem)")
endif()

# ── Python'u bul ──
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
message(STATUS "✅ Python: ${Python3_EXECUTABLE} (${Python3_VERSION})")

# ── Modül hedefi ──
pybind11_add_module(_memory_manager MODULE memory_manager.cpp)

# Platform-spesifik bağlantılar
if(APPLE)
    target_link_libraries(_memory_manager PRIVATE
        "-framework CoreFoundation"
    )
    message(STATUS "🍎 macOS platform desteği aktif")
elseif(UNIX)
    # Linux — ek bağımlılık gerekmiyor
    target_link_libraries(_memory_manager PRIVATE pthread)
    message(STATUS "🐧 Linux platform desteği aktif")
endif()

# Derleyici uyarıları
target_compile_options(_memory_manager PRIVATE
    -Wall -Wextra -Wpedantic
    $<$<CONFIG:Release>:-O3>
    $<$<CONFIG:Debug>:-g -O0>
)

# ── Çıktı dizini: memory_manager/ klasörüne koy ──
set_target_properties(_memory_manager PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}"
)

message(STATUS "")
message(STATUS "════════════════════════════════════════")
message(STATUS "  JARVIS Memory Manager — Derleme Hazır")
message(STATUS "════════════════════════════════════════")
message(STATUS "")
