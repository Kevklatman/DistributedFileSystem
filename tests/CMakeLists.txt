add_executable(storage_test storage_tests/storage_test.cpp)
add_executable(manager_test manager_tests/manager_test.cpp)

add_test(NAME StorageTest COMMAND storage_test)
add_test(NAME ManagerTest COMMAND manager_test)
set(CMAKE_CXX_STANDARD 17)