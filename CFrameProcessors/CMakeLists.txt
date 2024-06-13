cmake_minimum_required(VERSION 3.28)
project(CImageProcessing)

set(CMAKE_CXX_STANDARD 17)

include_directories(../lib)
add_subdirectory(pybind11)
#add_library(CImageProcessing SHARED lib/CFrameProcessors.cpp)
pybind11_add_module(CImageProcessing lib/CFrameProcessors.cpp)
target_compile_definitions(CImageProcessing
        PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})
