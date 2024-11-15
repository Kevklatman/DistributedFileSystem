cmake_minimum_required(VERSION 3.10)
project(DistributedFileSystem)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add source files
file(GLOB_RECURSE SOURCES "src/*.cpp")

# Create executable
add_executable(${PROJECT_NAME} ${SOURCES})

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}/include
    ${PROJECT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}  # For generated files
    /usr/local/include  # For gRPC
    /usr/local/include/zookeeper  # For ZooKeeper
    ${PROJECT_SOURCE_DIR}/proto  # Add this line for proto files
)

# Link libraries
target_link_libraries(${PROJECT_NAME} PRIVATE
    grpc++  # For gRPC
    zookeeper_mt  # For ZooKeeper
)

# Enable testing
enable_testing()
add_subdirectory(tests)
