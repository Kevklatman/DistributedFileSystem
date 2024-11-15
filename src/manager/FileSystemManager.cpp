#include "FileSystemManager.h"
#include <iostream>
#include <filesystem>

FileSystemManager::FileSystemManager() {
    // Initialize empty manager
}

void FileSystemManager::addStorageNode(const std::string& nodeId, const std::string& path) {
    nodes.push_back(std::make_unique<StorageNode>(nodeId, path));
    std::cout << "Added storage node: " << nodeId << " at path: " << path << std::endl;
}

bool FileSystemManager::writeFile(const std::string& filename, const std::string& content) {
    // For now, write to first available node
    if (nodes.empty()) {
        std::cout << "No storage nodes available" << std::endl;
        return false;
    }
    
    return nodes[0]->storeFile(filename, content);
}

std::string FileSystemManager::readFile(const std::string& filename) {
    // For now, read from first node that has the file
    for (const auto& node : nodes) {
        std::string content = node->retrieveFile(filename);
        if (!content.empty()) {
            return content;
        }
    }
    return "";
}

bool FileSystemManager::deleteFile(const std::string& filename) {
    // Try to delete from all nodes that might have the file
    bool deletedAny = false;
    for (const auto& node : nodes) {
        if (node->deleteFile(filename)) {
            deletedAny = true;
        }
    }
    return deletedAny;
}

std::vector<std::string> FileSystemManager::listAllFiles() {
    std::vector<std::string> allFiles;
    for (const auto& node : nodes) {
        auto nodeFiles = node->listFiles();
        allFiles.insert(allFiles.end(), nodeFiles.begin(), nodeFiles.end());
    }
    return allFiles;
}