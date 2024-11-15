cmake_minimum_required(VERSION 3.10)
project(DistributedFileSystem)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find protobuf installation
find_package(Protobuf REQUIRED)
include_directories(${Protobuf_INCLUDE_DIRS})

# Find gRPC
set(gRPC_DIR "/usr/local/lib/cmake/grpc")
find_package(absl REQUIRED)
find_package(gRPC REQUIRED)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/proto
    ${CMAKE_CURRENT_BINARY_DIR}
    ${PROTOBUF_INCLUDE_DIRS}
    /usr/local/include
)

link_directories(/usr/local/lib)

# Source files
set(SOURCES
    src/manager/FileSystemManager.cpp
    src/storage/StorageNode.cpp
    src/utils/Logger.cpp
    src/main.cpp
    proto/storage.grpc.pb.cc
    proto/storage.pb.cc
)

# Create executable
add_executable(${PROJECT_NAME} ${SOURCES})

# Link libraries
target_link_libraries(${PROJECT_NAME}
    ${PROTOBUF_LIBRARIES}
    gRPC::grpc++
    gRPC::grpc++_reflection
)

# Tests
add_executable(storage_test tests/storage_tests/storage_test.cpp)
add_executable(manager_test tests/manager_tests/manager_test.cpp)
