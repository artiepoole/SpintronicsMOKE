cmake_minimum_required(VERSION 3.28)
project(CImageProcessing)

set(CMAKE_CXX_STANDARD 17)

#find_package(Python3 COMPONENTS Development)
##include_directories(${Boost_INCLUDE_DIRS})
##target_link_libraries(CLionBoostRegex -static)
##target_link_libraries(CLionBoostRegex ${Boost_LIBRARIES})

include_directories(../lib)
add_subdirectory(pybind11)
#add_library(CImageProcessing SHARED lib/CFrameProcessors.cpp)
pybind11_add_module(CImageProcessing lib/CFrameProcessors.cpp)
target_compile_definitions(CImageProcessing
        PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})
