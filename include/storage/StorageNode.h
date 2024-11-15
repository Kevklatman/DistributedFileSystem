// include/storage/StorageNode.h
#ifndef STORAGE_NODE_H
#define STORAGE_NODE_H

#include <string>
#include <vector>
#include <map>
#include <filesystem>

class StorageNode
{
public:
    StorageNode(const std::string &nodeId, const std::string &basePath);

    // Basic operations
    bool storeFile(const std::string &filename, const std::string &content);
    std::string retrieveFile(const std::string &filename);
    bool deleteFile(const std::string &filename);
    std::vector<std::string> listFiles();

    // Node information
    const std::string &getNodeId() const { return nodeId; }
    const std::string &getBasePath() const { return basePath; }

    // Storage statistics
    size_t getFileCount() const;
    size_t getTotalSpaceUsed() const;
    double getDiskUsagePercentage() const;

private:
    std::string nodeId;
    std::string basePath;
    std::map<std::string, std::string> fileMap;

    bool ensureDirectoryExists() const;
    std::string getFullPath(const std::string &filename) const;
};

#endif // STORAGE_NODE_H
