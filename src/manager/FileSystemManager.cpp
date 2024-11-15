#include "FileSystemManager.h"
#include <iostream>
#include <filesystem>
#include <random>

FileSystemManager::FileSystemManager() {
    // Initialize empty manager
}

void FileSystemManager::addStorageNode(const std::string& nodeId, const std::string& path) {
    nodes.push_back(std::make_unique<StorageNode>(nodeId, path));
    std::cout << "Added storage node: " << nodeId << " at path: " << path << std::endl;
}

std::vector<std::string> FileSystemManager::listNodes() {
    std::vector<std::string> nodeIds;
    for (const auto& node : nodes) {
        nodeIds.push_back(node->getNodeId());
    }
    return nodeIds;
}

bool FileSystemManager::writeFileToNode(const std::string& nodeId, const std::string& filename, const std::string& content) {
    for (const auto& node : nodes) {
        if (node->getNodeId() == nodeId) {
            bool success = node->storeFile(filename, content);
            if (success) {
                std::cout << "File written to node: " << nodeId << std::endl;
            } else {
                std::cout << "Failed to write to node: " << nodeId << std::endl;
            }
            return success;
        }
    }
    std::cout << "Node not found: " << nodeId << std::endl;
    return false;
}

bool FileSystemManager::writeFile(const std::string& filename, const std::string& content) {
    if (nodes.empty()) {
        std::cout << "No storage nodes available" << std::endl;
        return false;
    }
    
    // Use a random node for better distribution
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, nodes.size() - 1);
    int nodeIndex = dis(gen);
    
    bool success = nodes[nodeIndex]->storeFile(filename, content);
    if (success) {
        std::cout << "File written to node: " << nodes[nodeIndex]->getNodeId() << std::endl;
    }
    return success;
}

std::string FileSystemManager::readFile(const std::string& filename) {
    for (const auto& node : nodes) {
        std::string content = node->retrieveFile(filename);
        if (!content.empty()) {
            std::cout << "File found in node: " << node->getNodeId() << std::endl;
            return content;
        }
    }
    std::cout << "File not found in any node" << std::endl;
    return "";
}

bool FileSystemManager::deleteFile(const std::string& filename) {
    bool deletedAny = false;
    for (const auto& node : nodes) {
        if (node->deleteFile(filename)) {
            std::cout << "File deleted from node: " << node->getNodeId() << std::endl;
            deletedAny = true;
        }
    }
    return deletedAny;
}

std::vector<std::string> FileSystemManager::listAllFiles() {
    std::vector<std::string> allFiles;
    for (const auto& node : nodes) {
        std::cout << "\nFiles in node " << node->getNodeId() << ":\n";
        auto nodeFiles = node->listFiles();
        for (const auto& file : nodeFiles) {
            std::cout << "- " << file << std::endl;
        }
        allFiles.insert(allFiles.end(), nodeFiles.begin(), nodeFiles.end());
    }
    return allFiles;
}

std::string FileSystemManager::formatSize(size_t bytes) const {
    const char* units[] = {"B", "KB", "MB", "GB"};
    int unitIndex = 0;
    double size = static_cast<double>(bytes);
    
    while (size >= 1024 && unitIndex < 3) {
        size /= 1024;
        unitIndex++;
    }
    
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%.2f %s", size, units[unitIndex]);
    return std::string(buffer);
}

void FileSystemManager::displayNodeStatus() {
    if (nodes.empty()) {
        std::cout << "No storage nodes available\n";
        return;
    }

    std::cout << "\n=== Node Status ===\n";
    for (const auto& node : nodes) {
        std::cout << "\n📁 Node ID: " << node->getNodeId() << "\n";
        std::cout << "   Path: " << node->getBasePath() << "\n";
        std::cout << "   Files stored: " << node->getFileCount() << "\n";
        std::cout << "   Space used: " << formatSize(node->getTotalSpaceUsed()) << "\n";
        std::cout << "   Disk usage: " << std::fixed << std::setprecision(2) 
                  << node->getDiskUsagePercentage() << "%\n";
        
        // List files in this node
        auto files = node->listFiles();
        if (!files.empty()) {
            std::cout << "   Files:\n";
            for (const auto& file : files) {
                std::cout << "   - " << file << "\n";
            }
        }
        std::cout << "   -------------------\n";
    }
}