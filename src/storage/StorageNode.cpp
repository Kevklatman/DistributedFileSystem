#include "StorageNode.h"
#include <fstream>
#include <filesystem>
#include <iostream>

StorageNode::StorageNode(const std::string& id, const std::string& path) 
    : nodeId(id), basePath(path) {
    // Create directory if it doesn't exist
    std::filesystem::create_directories(basePath);
}

bool StorageNode::storeFile(const std::string& filename, const std::string& content) {
    std::string filepath = basePath + "/" + filename;
    try {
        std::ofstream file(filepath);
        if (!file) {
            return false;
        }
        file << content;
        fileMap[filename] = filepath;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Error storing file: " << e.what() << std::endl;
        return false;
    }
}

std::string StorageNode::retrieveFile(const std::string& filename) {
    auto it = fileMap.find(filename);
    if (it == fileMap.end()) {
        return "";
    }
    
    try {
        std::ifstream file(it->second);
        if (!file) {
            return "";
        }
        return std::string((std::istreambuf_iterator<char>(file)),
                           std::istreambuf_iterator<char>());
    } catch (const std::exception& e) {
        std::cerr << "Error retrieving file: " << e.what() << std::endl;
        return "";
    }
}

bool StorageNode::deleteFile(const std::string& filename) {
    auto it = fileMap.find(filename);
    if (it == fileMap.end()) {
        return false;
    }
    
    try {
        std::filesystem::remove(it->second);
        fileMap.erase(it);
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Error deleting file: " << e.what() << std::endl;
        return false;
    }
}

std::vector<std::string> StorageNode::listFiles() {
    std::vector<std::string> files;
    for (const auto& [filename, _] : fileMap) {
        files.push_back(filename);
    }
    return files;
}