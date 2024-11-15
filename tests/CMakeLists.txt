cmake_minimum_required(VERSION 3.10)
project(DistributedFS VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Ensure protobuf compatibility
set(protobuf_MODULE_COMPATIBLE TRUE)
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)
find_package(OpenSSL REQUIRED)

# Set proto directory
set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/proto)

# Verify proto directory exists
if(NOT EXISTS ${PROTO_DIR})
    message(FATAL_ERROR "Proto directory not found: ${PROTO_DIR}")
endif()

# Proto files
set(PROTO_FILES ${PROTO_DIR}/storage.proto)

# Verify proto file exists
if(NOT EXISTS ${PROTO_FILES})
    message(FATAL_ERROR "Proto file not found: ${PROTO_FILES}")
endif()

# Generate protobuf and gRPC code
add_custom_command(
    OUTPUT
        "${CMAKE_CURRENT_BINARY_DIR}/storage.pb.cc"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.pb.h"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.grpc.pb.cc"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.grpc.pb.h"
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
    ARGS --grpc_out="${CMAKE_CURRENT_BINARY_DIR}"
         --cpp_out="${CMAKE_CURRENT_BINARY_DIR}"
         --proto_path="${PROTO_DIR}/.."
         --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
         "proto/storage.proto"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    DEPENDS ${PROTO_FILES}
    VERBATIM
)

# Create a custom target for proto generation
add_custom_target(generate_protos ALL
    DEPENDS
        "${CMAKE_CURRENT_BINARY_DIR}/storage.pb.cc"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.pb.h"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.grpc.pb.cc"
        "${CMAKE_CURRENT_BINARY_DIR}/storage.grpc.pb.h"
)

# Storage proto library
add_library(storage_proto
    "${CMAKE_CURRENT_BINARY_DIR}/storage.pb.cc"
    "${CMAKE_CURRENT_BINARY_DIR}/storage.grpc.pb.cc"
)

# Add dependency on proto generation
add_dependencies(storage_proto generate_protos)

target_link_libraries(storage_proto
    PUBLIC
        ${Protobuf_LIBRARIES}
        gRPC::grpc++
        gRPC::grpc++_reflection
)

target_include_directories(storage_proto PUBLIC
    ${CMAKE_CURRENT_BINARY_DIR}
    ${Protobuf_INCLUDE_DIRS}
)

# Core library
add_library(dfs_core
    src/storage/StorageNode.cpp
    src/manager/FileSystemManager.cpp
    src/storage/storage_service.cpp
)

target_link_libraries(dfs_core
    PUBLIC
        storage_proto
        OpenSSL::SSL
        OpenSSL::Crypto
)

target_include_directories(dfs_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Executables
add_executable(storage_server src/storage/storage_server.cpp)
target_link_libraries(storage_server PRIVATE dfs_core)

add_executable(dfs_main src/main.cpp)
target_link_libraries(dfs_main PRIVATE dfs_core)

# Tests
add_executable(storage_test tests/storage_tests/storage_test.cpp)
add_executable(manager_test tests/manager_tests/manager_test.cpp)

target_link_libraries(storage_test PRIVATE dfs_core)
target_link_libraries(manager_test PRIVATE dfs_core)

add_test(NAME StorageTest COMMAND storage_test)
add_test(NAME ManagerTest COMMAND manager_test)

# Debug output
message(STATUS "Project source dir: ${CMAKE_CURRENT_SOURCE_DIR}")
message(STATUS "Proto dir: ${PROTO_DIR}")
message(STATUS "Proto files: ${PROTO_FILES}")
message(STATUS "Protoc executable: ${Protobuf_PROTOC_EXECUTABLE}")
