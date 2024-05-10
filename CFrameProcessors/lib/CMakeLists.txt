cmake_minimum_required(VERSION 3.28)
project(CImageProcessing)

set(CMAKE_CXX_STANDARD 17)

add_library(CImageProcessing SHARED lib/CFrameProcessors.c)