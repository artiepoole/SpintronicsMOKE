cmake_minimum_required(VERSION 3.28)
project(CImageProcessing)

set(CMAKE_CXX_STANDARD 17)

include_directories(../lib)
add_subdirectory(pybind11)

find_package(OpenMP REQUIRED)

#add_library(CImageProcessing SHARED lib/CFrameProcessors.cpp)
pybind11_add_module(CImageProcessing lib/CFrameProcessors.cpp)
target_compile_definitions(CImageProcessing
        PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})
#if (OPENMP_FOUND)
set (CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OpenMP_C_FLAGS}")
set (CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
set (CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${OpenMP_EXE_LINKER_FLAGS}")
#endif()