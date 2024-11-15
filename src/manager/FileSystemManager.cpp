#include "FileSystemManager.h"
#include <iostream>
#include <filesystem>
#include <random>
#include <algorithm>
#include <set>
#include <sstream>
#include <chrono>
#include <thread>
#include <future>
#include <shared_mutex>

FileSystemManager::FileSystemManager() : maxRetries(3) {}

FileSystemManager::FileSystemManager(int retries) : maxRetries(retries) {}

void FileSystemManager::addStorageNode(const std::string& nodeId, const std::string& path) {
    if (std::find_if(nodes.begin(), nodes.end(), 
        [&nodeId](const auto& node) { return node->getNodeId() == nodeId; }) != nodes.end()) {
        throw std::runtime_error("Node ID already exists: " + nodeId);
    }

    try {
        nodes.push_back(std::make_unique<StorageNode>(nodeId, path));
        std::cout << "Added storage node: " << nodeId << " at path: " << path << std::endl;
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to add storage node: " + std::string(e.what()));
    }
}

std::vector<std::string> FileSystemManager::listNodes() const {
    std::vector<std::string> nodeIds;
    nodeIds.reserve(nodes.size());
    std::transform(nodes.begin(), nodes.end(), std::back_inserter(nodeIds),
                  [](const auto& node) { return node->getNodeId(); });
    return nodeIds;
}

std::vector<std::string> FileSystemManager::searchByName(const std::string& pattern) const {
    std::vector<std::string> results;
    for (const auto& node : nodes) {
        try {
            auto nodeFiles = node->listFiles();
            for (const auto& file : nodeFiles) {
                if (file.find(pattern) != std::string::npos) {
                    results.push_back(file + " (Node: " + node->getNodeId() + ")");
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "Error searching in node " << node->getNodeId() << ": " << e.what() << std::endl;
        }
    }
    return results;
}

std::vector<std::string> FileSystemManager::searchByContent(const std::string& pattern) const {
    std::vector<std::string> results;
    std::mutex resultsMutex;
    std::vector<std::future<void>> searches;

    for (const auto& node : nodes) {
        searches.push_back(std::async(std::launch::async, [&, node = node.get()]() {
            try {
                auto nodeFiles = node->listFiles();
                for (const auto& file : nodeFiles) {
                    std::string content = node->retrieveFile(file);
                    if (content.find(pattern) != std::string::npos) {
                        std::lock_guard<std::mutex> lock(resultsMutex);
                        results.push_back(file + " (Node: " + node->getNodeId() + ")");
                    }
                }
            } catch (const std::exception& e) {
                std::cerr << "Error searching in node " << node->getNodeId() << ": " << e.what() << std::endl;
            }
        }));
    }

    for (auto& search : searches) {
        search.wait();
    }
    
    return results;
}

std::vector<std::string> FileSystemManager::searchByMetadata(
    const std::string& key, const std::string& value) const {
    std::vector<std::string> results;
    std::shared_lock<std::shared_mutex> lock(metadataMutex);
    
    for (const auto& [filename, metadata] : fileMetadata) {
        auto it = metadata.attributes.find(key);
        if (it != metadata.attributes.end() && it->second == value) {
            results.push_back(filename);
        }
    }
    return results;
}

bool FileSystemManager::createDirectory(const std::string& dirPath) {
    if (!isValidPath(dirPath)) {
        throw std::invalid_argument("Invalid directory path. Must start with '/'");
    }

    bool success = true;
    std::vector<std::string> failedNodes;

    for (const auto& node : nodes) {
        std::string fullPath = node->getBasePath() + dirPath;
        try {
            if (!std::filesystem::create_directories(fullPath)) {
                failedNodes.push_back(node->getNodeId());
                success = false;
            }
        } catch (const std::filesystem::filesystem_error& e) {
            failedNodes.push_back(node->getNodeId());
            success = false;
        }
    }

    if (!failedNodes.empty()) {
        std::stringstream ss;
        ss << "Failed to create directory in nodes: ";
        for (const auto& nodeId : failedNodes) {
            ss << nodeId << " ";
        }
        throw std::runtime_error(ss.str());
    }

    return success;
}

bool FileSystemManager::moveToDirectory(const std::string& filename, const std::string& dirPath) {
    if (!isValidDirectory(dirPath)) {
        throw std::invalid_argument("Invalid directory path");
    }

    {
        std::unique_lock<std::shared_mutex> lock(metadataMutex);
        if (fileMetadata.find(filename) != fileMetadata.end()) {
            fileMetadata[filename].directory = dirPath;
        } else {
            FileMetadata metadata;
            metadata.directory = dirPath;
            fileMetadata[filename] = metadata;
        }
    }

    bool found = false;
    std::vector<std::string> errors;

    for (const auto& node : nodes) {
        try {
            std::string content = node->retrieveFile(filename);
            if (!content.empty()) {
                std::string newPath = dirPath + "/" + filename;
                if (node->storeFile(newPath, content)) {
                    if (!node->deleteFile(filename)) {
                        errors.push_back("Failed to delete original file in node: " + node->getNodeId());
                    }
                    found = true;
                } else {
                    errors.push_back("Failed to store file in new location in node: " + node->getNodeId());
                }
            }
        } catch (const std::exception& e) {
            errors.push_back("Error in node " + node->getNodeId() + ": " + e.what());
        }
    }

    if (!errors.empty()) {
        std::stringstream ss;
        ss << "Errors occurred during move operation:\n";
        for (const auto& error : errors) {
            ss << error << "\n";
        }
        throw std::runtime_error(ss.str());
    }

    return found;
}

// Add these implementations to FileSystemManager.cpp

std::vector<std::string> FileSystemManager::searchByName(const std::string& pattern) {
    std::vector<std::string> results;
    for (const auto& node : nodes) {
        auto nodeFiles = node->listFiles();
        for (const auto& file : nodeFiles) {
            if (file.find(pattern) != std::string::npos) {
                results.push_back(file + " (Node: " + node->getNodeId() + ")");
            }
        }
    }
    return results;
}

std::vector<std::string> FileSystemManager::searchByContent(const std::string& pattern) {
    std::vector<std::string> results;
    for (const auto& node : nodes) {
        auto nodeFiles = node->listFiles();
        for (const auto& file : nodeFiles) {
            std::string content = node->retrieveFile(file);
            if (content.find(pattern) != std::string::npos) {
                results.push_back(file + " (Node: " + node->getNodeId() + ")");
            }
        }
    }
    return results;
}

std::vector<std::string> FileSystemManager::searchByMetadata(const std::string& key, const std::string& value) {
    std::vector<std::string> results;
    for (const auto& [filename, metadata] : fileMetadata) {
        auto it = metadata.attributes.find(key);
        if (it != metadata.attributes.end() && it->second == value) {
            results.push_back(filename);
        }
    }
    return results;
}

bool FileSystemManager::createDirectory(const std::string& dirPath) {
    if (dirPath.empty() || dirPath[0] != '/') {
        std::cout << "Invalid directory path. Must start with '/'\n";
        return false;
    }

    // Create directory in all nodes for consistency
    bool success = true;
    for (const auto& node : nodes) {
        std::string fullPath = node->getBasePath() + dirPath;
        try {
            std::filesystem::create_directories(fullPath);
        } catch (const std::filesystem::filesystem_error& e) {
            std::cout << "Error creating directory in node " << node->getNodeId() 
                     << ": " << e.what() << "\n";
            success = false;
        }
    }
    return success;
}
bool FileSystemManager::isValidPath(const std::string& path) const {
    return !path.empty() && path[0] == '/' && 
           path.find("..") == std::string::npos;
}

std::string FileSystemManager::normalizeFilepath(const std::string& path) const {
    std::filesystem::path normalized = std::filesystem::path(path).lexically_normal();
    return normalized.string();
}

StorageNode* FileSystemManager::selectOptimalNode() const {
    // Simple round-robin selection for demonstration
    static size_t lastIndex = 0;
    if (nodes.empty()) return nullptr;
    
    lastIndex = (lastIndex + 1) % nodes.size();
    return nodes[lastIndex].get();
}

void FileSystemManager::validateNodeExists(const std::string& nodeId) const {
    if (std::none_of(nodes.begin(), nodes.end(),
        [&nodeId](const auto& node) { return node->getNodeId() == nodeId; })) {
        throw std::runtime_error("Node not found: " + nodeId);
    }
}
bool FileSystemManager::moveToDirectory(const std::string& filename, const std::string& dirPath) {
    if (!isValidDirectory(dirPath)) {
        std::cout << "Invalid directory path\n";
        return false;
    }

    // Update metadata
    if (fileMetadata.find(filename) != fileMetadata.end()) {
        fileMetadata[filename].directory = dirPath;
    } else {
        FileMetadata metadata;
        metadata.directory = dirPath;
        fileMetadata[filename] = metadata;
    }

    // Move actual file in all nodes
    bool found = false;
    for (const auto& node : nodes) {
        std::string content = node->retrieveFile(filename);
        if (!content.empty()) {
            std::string newPath = dirPath + "/" + filename;
            if (node->storeFile(newPath, content)) {
                node->deleteFile(filename);
                found = true;
            }
        }
    }

    return found;
}

std::vector<std::string> FileSystemManager::listDirectory(const std::string& dirPath) {
    std::vector<std::string> files;
    std::set<std::string> uniqueFiles; // To avoid duplicates from different nodes

    for (const auto& node : nodes) {
        std::string fullPath = node->getBasePath() + dirPath;
        try {
            for (const auto& entry : std::filesystem::directory_iterator(fullPath)) {
                if (entry.is_regular_file()) {
                    uniqueFiles.insert(entry.path().filename().string());
                }
            }
        } catch (const std::filesystem::filesystem_error& e) {
            std::cout << "Error reading directory in node " << node->getNodeId() 
                     << ": " << e.what() << "\n";
        }
    }

    files.insert(files.end(), uniqueFiles.begin(), uniqueFiles.end());
    return files;
}

bool FileSystemManager::addMetadata(const std::string& filename, 
                                  const std::string& key, 
                                  const std::string& value) {
    // Verify file exists
    bool fileExists = false;
    for (const auto& node : nodes) {
        if (!node->retrieveFile(filename).empty()) {
            fileExists = true;
            break;
        }
    }

    if (!fileExists) {
        std::cout << "File not found\n";
        return false;
    }

    // Add or update metadata
    fileMetadata[filename].attributes[key] = value;
    return true;
}

std::map<std::string, std::string> FileSystemManager::getMetadata(const std::string& filename) {
    auto it = fileMetadata.find(filename);
    if (it != fileMetadata.end()) {
        return it->second.attributes;
    }
    return std::map<std::string, std::string>();
}

bool FileSystemManager::isValidDirectory(const std::string& dirPath) const {
    if (dirPath.empty() || dirPath[0] != '/') {
        return false;
    }

    // Check if directory exists in at least one node
    for (const auto& node : nodes) {
        std::string fullPath = node->getBasePath() + dirPath;
        if (std::filesystem::exists(fullPath) && 
            std::filesystem::is_directory(fullPath)) {
            return true;
        }
    }
    return false;
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

// FileSystemManager.cpp additions

bool FileSystemManager::replicateFile(const std::string& filename, int copies) {
    // First, find the original file
    std::string content;
    std::string sourceNodeId;
    
    for (const auto& node : nodes) {
        content = node->retrieveFile(filename);
        if (!content.empty()) {
            sourceNodeId = node->getNodeId();
            break;
        }
    }
    
    if (content.empty()) {
        std::cout << "Original file not found\n";
        return false;
    }

    int successfulCopies = 0;
    std::vector<std::string> usedNodes = {sourceNodeId};

    // Create specified number of copies
    for (int i = 0; i < copies; i++) {
        // Find a node that doesn't have this file
        for (const auto& node : nodes) {
            if (std::find(usedNodes.begin(), usedNodes.end(), 
                         node->getNodeId()) == usedNodes.end()) {
                if (node->storeFile(filename, content)) {
                    usedNodes.push_back(node->getNodeId());
                    successfulCopies++;
                    std::cout << "Created copy on node: " << node->getNodeId() << "\n";
                    break;
                }
            }
        }
    }

    std::cout << "Created " << successfulCopies << " copies of " << filename << "\n";
    return successfulCopies == copies;
}

bool FileSystemManager::moveFile(const std::string& filename,
                               const std::string& sourceNode,
                               const std::string& targetNode) {
    // Find source and target nodes
    StorageNode* source = nullptr;
    StorageNode* target = nullptr;

    for (const auto& node : nodes) {
        if (node->getNodeId() == sourceNode) source = node.get();
        if (node->getNodeId() == targetNode) target = node.get();
    }

    if (!source || !target) {
        std::cout << "Source or target node not found\n";
        return false;
    }

    // Get file content from source
    std::string content = source->retrieveFile(filename);
    if (content.empty()) {
        std::cout << "File not found in source node\n";
        return false;
    }

    // Store in target and delete from source
    if (target->storeFile(filename, content)) {
        if (source->deleteFile(filename)) {
            std::cout << "File moved successfully\n";
            return true;
        }
        // If delete fails, rollback the target storage
        target->deleteFile(filename);
    }

    std::cout << "Failed to move file\n";
    return false;
}

bool FileSystemManager::compressFile(const std::string& filename) {
    if (isFileCompressed(filename)) {
        std::cout << "File is already compressed\n";
        return false;
    }

    std::string content;
    StorageNode* fileNode = nullptr;

    // Find the file
    for (const auto& node : nodes) {
        content = node->retrieveFile(filename);
        if (!content.empty()) {
            fileNode = node.get();
            break;
        }
    }

    if (!fileNode) {
        std::cout << "File not found\n";
        return false;
    }

    // Compress content
    std::string compressed = compressContent(content);
    
    // Store compressed version
    std::string compressedFilename = filename + ".gz";
    if (fileNode->storeFile(compressedFilename, compressed)) {
        fileNode->deleteFile(filename);
        std::cout << "File compressed successfully\n";
        return true;
    }

    return false;
}

bool FileSystemManager::decompressFile(const std::string& filename) {
    if (!isFileCompressed(filename)) {
        std::cout << "File is not compressed\n";
        return false;
    }

    std::string compressed;
    StorageNode* fileNode = nullptr;

    // Find the compressed file
    for (const auto& node : nodes) {
        compressed = node->retrieveFile(filename);
        if (!compressed.empty()) {
            fileNode = node.get();
            break;
        }
    }

    if (!fileNode) {
        std::cout << "Compressed file not found\n";
        return false;
    }

    // Decompress content
    std::string decompressed = decompressContent(compressed);
    
    // Store decompressed version
    std::string decompressedFilename = filename.substr(0, filename.length() - 3); // Remove .gz
    if (fileNode->storeFile(decompressedFilename, decompressed)) {
        fileNode->deleteFile(filename);
        std::cout << "File decompressed successfully\n";
        return true;
    }

    return false;
}

// Helper methods
bool FileSystemManager::isFileCompressed(const std::string& filename) {
    return filename.length() > 3 && 
           filename.substr(filename.length() - 3) == ".gz";
}

std::string FileSystemManager::compressContent(const std::string& content) {
    // Simple run-length encoding for demonstration
    // In a real system, use a proper compression library like zlib
    std::string compressed;
    for (size_t i = 0; i < content.length(); i++) {
        char current = content[i];
        int count = 1;
        while (i + 1 < content.length() && content[i + 1] == current) {
            count++;
            i++;
        }
        compressed += std::to_string(count) + current;
    }
    return compressed;
}

void FileSystemManager::addStorageNode(const std::string& nodeId, const std::string& path) {
    nodes.push_back(std::make_unique<StorageNode>(nodeId, path));
}

bool FileSystemManager::writeFile(const std::string& filename, const std::string& content) {
    if (nodes.empty()) {
        return false;
    }
    // Simple round-robin or random node selection
    size_t nodeIndex = rand() % nodes.size();
    return nodes[nodeIndex]->storeFile(filename, content);
}

bool FileSystemManager::writeFileToNode(const std::string& nodeId, 
                                      const std::string& filename, 
                                      const std::string& content) {
    auto it = std::find_if(nodes.begin(), nodes.end(),
        [&nodeId](const auto& node) { return node->getNodeId() == nodeId; });
    
    if (it != nodes.end()) {
        return (*it)->storeFile(filename, content);
    }
    return false;
}

std::string FileSystemManager::readFile(const std::string& filename) {
    for (const auto& node : nodes) {
        std::string content = node->retrieveFile(filename);
        if (!content.empty()) {
            return content;
        }
    }
    return "";
}

bool FileSystemManager::deleteFile(const std::string& filename) {
    bool deleted = false;
    for (const auto& node : nodes) {
        if (node->deleteFile(filename)) {
            deleted = true;
        }
    }
    return deleted;
}

std::vector<std::string> FileSystemManager::listAllFiles() {
    std::vector<std::string> allFiles;
    for (const auto& node : nodes) {
        auto nodeFiles = node->listFiles();
        allFiles.insert(allFiles.end(), nodeFiles.begin(), nodeFiles.end());
    }
    return allFiles;
}

std::vector<std::string> FileSystemManager::listNodes() {
    std::vector<std::string> nodeIds;
    for (const auto& node : nodes) {
        nodeIds.push_back(node->getNodeId());
    }
    return nodeIds;
}

void FileSystemManager::displayNodeStatus() {
    for (const auto& node : nodes) {
        std::cout << "\nNode ID: " << node->getNodeId() << "\n"
                  << "Base Path: " << node->getBasePath() << "\n"
                  << "File Count: " << node->getFileCount() << "\n"
                  << "Total Space Used: " << formatSize(node->getTotalSpaceUsed()) << "\n"
                  << "Disk Usage: " << std::fixed << std::setprecision(2) 
                  << node->getDiskUsagePercentage() << "%\n";
    }
}

std::string FileSystemManager::decompressContent(const std::string& compressed) {
    // Simple run-length decoding
    std::string decompressed;
    std::string count;
    for (size_t i = 0; i < compressed.length(); i++) {
        if (isdigit(compressed[i])) {
            count += compressed[i];
        } else {
            int repeat = std::stoi(count);
            decompressed.append(repeat, compressed[i]);
            count.clear();
        }
    }
    return decompressed;
}