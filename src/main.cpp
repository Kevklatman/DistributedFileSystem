#include <iostream>
#include "manager/FileSystemManager.h"

int main() {
    std::cout << "Distributed File System Starting..." << std::endl;
    
    FileSystemManager fsManager;
    
    // Add some storage nodes
    fsManager.addStorageNode("node1", "./storage1");
    fsManager.addStorageNode("node2", "./storage2");
    
    // Example usage
    std::cout << "Writing file..." << std::endl;
    fsManager.writeFile("test.txt", "Hello, distributed world!");
    
    std::cout << "Reading file..." << std::endl;
    std::string content = fsManager.readFile("test.txt");
    std::cout << "Content: " << content << std::endl;
    
    std::cout << "Listing all files:" << std::endl;
    auto files = fsManager.listAllFiles();
    for (const auto& file : files) {
        std::cout << "- " << file << std::endl;
    }
    
    return 0;
}