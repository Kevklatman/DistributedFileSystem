#include "StorageNode.h"
#include <fstream>
#include <iostream>
#include <filesystem>

namespace fs = std::filesystem;

StorageNode::StorageNode(const std::string& id, const std::string& path) : nodeId(id), basePath(path) {
    if (!fs::exists(path)) {
        fs::create_directory(path);
    }
}

bool StorageNode::storeFile(const std::string& filename, const std::string& content) {
    try {
        std::string fullPath = basePath + "/" + filename;
        std::ofstream file(fullPath);
        if (file.is_open()) {
            file << content;
            file.close();
            fileMap[filename] = fullPath;
            return true;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error storing file: " << e.what() << std::endl;
    }
    return false;
}

std::string StorageNode::retrieveFile(const std::string& filename) {
    auto it = fileMap.find(filename);
    if (it != fileMap.end()) {
        try {
            std::ifstream file(it->second);
            if (file.is_open()) {
                return std::string((std::istreambuf_iterator<char>(file)),
                                 std::istreambuf_iterator<char>());
            }
        } catch (const std::exception& e) {
            std::cerr << "Error retrieving file: " << e.what() << std::endl;
        }
    }
    return "";
}

bool StorageNode::deleteFile(const std::string& filename) {
    auto it = fileMap.find(filename);
    if (it != fileMap.end()) {
        try {
            fs::remove(it->second);
            fileMap.erase(it);
            return true;
        } catch (const std::exception& e) {
            std::cerr << "Error deleting file: " << e.what() << std::endl;
        }
    }
    return false;
}

std::vector<std::string> StorageNode::listFiles() {
    std::vector<std::string> files;
    for (const auto& pair : fileMap) {
        files.push_back(pair.first);
    }
    return files;
}

size_t StorageNode::getTotalSpaceUsed() const {
    size_t totalSize = 0;
    try {
        for (const auto& entry : fs::directory_iterator(basePath)) {
            totalSize += fs::file_size(entry.path());
        }
    } catch (const std::exception& e) {
        std::cerr << "Error calculating space: " << e.what() << std::endl;
    }
    return totalSize;
}

double StorageNode::getDiskUsagePercentage() const {
    try {
        fs::space_info space = fs::space(basePath);
        double usedSpace = static_cast<double>(space.capacity - space.available);
        return (usedSpace / space.capacity) * 100.0;
    } catch (const std::exception& e) {
        std::cerr << "Error calculating disk usage: " << e.what() << std::endl;
        return 0.0;
    }
}