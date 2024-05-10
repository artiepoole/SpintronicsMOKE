cmake_minimum_required(VERSION 3.28)
project(CImageProcessing)

set(CMAKE_CXX_STANDARD 17)
set(TARGET_NAME playing)

set(SOURCE_FILES generate_hist.c)
add_library(mylib STATIC ../lib/CFrameProcessors.c
        ../lib/CFrameProcessors.c)
include_directories(../lib)

add_executable(playing ${SOURCE_FILES})

target_link_libraries(playing mylib)