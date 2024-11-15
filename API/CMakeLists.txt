cmake_minimum_required(VERSION 3.10)
project(fs_manager_python)

# Find Python
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Add pybind11
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/pybind11 ${CMAKE_CURRENT_BINARY_DIR}/pybind11)

# Add the Python module
pybind11_add_module(fs_manager fs_manager_binding.cpp)

# Include directories
target_include_directories(fs_manager PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

# Link against your FileSystemManager library
target_link_libraries(fs_manager PRIVATE dfs_manager)
