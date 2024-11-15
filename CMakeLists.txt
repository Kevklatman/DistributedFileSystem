cmake_minimum_required(VERSION 3.10)
project(DistributedFileSystem)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add source files
file(GLOB_RECURSE SOURCES
    "${PROJECT_SOURCE_DIR}/src/*.cpp"
)

# Create executable
add_executable(${PROJECT_NAME} ${SOURCES})

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}/include
)

# Print some debug information
message(STATUS "Source files: ${SOURCES}")
message(STATUS "Include directories: ${PROJECT_SOURCE_DIR}/include")
