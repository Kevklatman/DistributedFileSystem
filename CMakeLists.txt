cmake_minimum_required(VERSION 3.10)
project(DistributedFS VERSION 1.0)

# Basic setup
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
enable_testing()

# Find dependencies using CMake's built-in modules
find_package(OpenSSL REQUIRED)
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find gRPC and Protobuf
find_package(gRPC CONFIG QUIET)
if(NOT gRPC_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(GRPC REQUIRED grpc++)
    pkg_check_modules(PROTOBUF REQUIRED protobuf)
else()
    set(GRPC_LIBRARIES gRPC::grpc++)
    set(PROTOBUF_LIBRARIES protobuf::libprotobuf)
endif()

# Find protoc and gRPC plugin
find_program(PROTOC protoc REQUIRED)
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin REQUIRED)

# Proto file setup
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/proto/storage.proto")
set(GENERATED_PROTO_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")

if(NOT EXISTS ${PROTO_FILE})
    message(FATAL_ERROR "Proto file not found: ${PROTO_FILE}")
endif()

file(MAKE_DIRECTORY ${GENERATED_PROTO_DIR})

# Generate protobuf and gRPC code
add_custom_command(
    OUTPUT
        "${GENERATED_PROTO_DIR}/storage.pb.cc"
        "${GENERATED_PROTO_DIR}/storage.pb.h"
        "${GENERATED_PROTO_DIR}/storage.grpc.pb.cc"
        "${GENERATED_PROTO_DIR}/storage.grpc.pb.h"
    COMMAND ${PROTOC}
        --grpc_out=${GENERATED_PROTO_DIR}
        --cpp_out=${GENERATED_PROTO_DIR}
        --proto_path=${CMAKE_CURRENT_SOURCE_DIR}/proto
        --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
        ${PROTO_FILE}
    DEPENDS ${PROTO_FILE}
    VERBATIM
)

add_custom_target(generate_protos ALL
    DEPENDS
        "${GENERATED_PROTO_DIR}/storage.pb.cc"
        "${GENERATED_PROTO_DIR}/storage.pb.h"
        "${GENERATED_PROTO_DIR}/storage.grpc.pb.cc"
        "${GENERATED_PROTO_DIR}/storage.grpc.pb.h"
)

# Storage proto library
add_library(storage_proto
    "${GENERATED_PROTO_DIR}/storage.pb.cc"
    "${GENERATED_PROTO_DIR}/storage.grpc.pb.cc"
)

add_dependencies(storage_proto generate_protos)

target_include_directories(storage_proto PUBLIC
    ${GENERATED_PROTO_DIR}
    ${PROTOBUF_INCLUDE_DIRS}
    ${GRPC_INCLUDE_DIRS}
)

target_link_libraries(storage_proto PUBLIC
    ${PROTOBUF_LIBRARIES}
    ${GRPC_LIBRARIES}
)

# Add pybind11
add_subdirectory(third_party/pybind11)

# Core library
add_library(dfs_core
    src/storage/StorageNode.cpp
    src/manager/FileSystemManager.cpp
    src/storage/storage_service.cpp
)

target_include_directories(dfs_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/include/storage
    ${CMAKE_CURRENT_SOURCE_DIR}/include/manager
    ${CMAKE_CURRENT_SOURCE_DIR}/include/utils
)

target_link_libraries(dfs_core PUBLIC
    storage_proto
    OpenSSL::SSL
    OpenSSL::Crypto
)

# Python bindings
pybind11_add_module(fs_manager api/fs_manager_binding.cpp)
target_include_directories(fs_manager PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(fs_manager PRIVATE dfs_core)

# Function to add executable with common libraries
function(add_dfs_executable target_name source_file)
    add_executable(${target_name} ${source_file})
    target_link_libraries(${target_name} PRIVATE dfs_core)
endfunction()

# Add executables
add_dfs_executable(storage_server src/storage/storage_server.cpp)
add_dfs_executable(dfs_main src/main.cpp)
add_dfs_executable(dfs_cli src/main.cpp)

# Add tests
add_dfs_executable(storage_test tests/storage_tests/storage_test.cpp)
add_dfs_executable(manager_test tests/manager_tests/manager_test.cpp)

# Register tests
add_test(NAME StorageTest COMMAND storage_test)
add_test(NAME ManagerTest COMMAND manager_test)
