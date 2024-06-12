cmake_minimum_required(VERSION 3.28)
project(lib)

set(CMAKE_CXX_STANDARD 17)
set(TARGET_NAME lib)

add_library(CImageProcessing SHARED CFrameProcessors.cpp)