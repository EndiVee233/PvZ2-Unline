cmake_minimum_required(VERSION 3.22)
project(glshim CXX)

set(OPTION_ASTC_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../astc-codec ${CMAKE_CURRENT_BINARY_DIR}/astc-codec)

add_library(glshim SHARED glshim.cpp)
set(PVZ2_PREFETCH_INDEX "" CACHE FILEPATH "Generated prefetch_index.inc for the resource release")
if(PVZ2_PREFETCH_INDEX)
    configure_file(${PVZ2_PREFETCH_INDEX} ${CMAKE_CURRENT_BINARY_DIR}/prefetch_index.inc COPYONLY)
else()
    file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/prefetch_index.inc
        "static const PrefetchTexture kPrefetchTextures[1] = {};\nstatic const size_t kPrefetchTextureCount = 0;\n")
endif()
target_include_directories(glshim PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_compile_features(glshim PRIVATE cxx_std_17)
target_compile_options(glshim PRIVATE -fno-exceptions -fno-rtti -O2)
target_include_directories(glshim PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../astc-codec/include)
target_link_libraries(glshim log android dl z astc-codec)
