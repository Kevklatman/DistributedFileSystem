// include/manager/FileSystemManager.h
#ifndef FILE_SYSTEM_MANAGER_H
#define FILE_SYSTEM_MANAGER_H

#include <string>
#include <vector>
#include <memory>
#include <map>
#include "storage/StorageNode.h"

class FileSystemManager
{
public:
    FileSystemManager();
    explicit FileSystemManager(int maxRetries);

    // Node management
    void addStorageNode(const std::string &nodeId, const std::string &path);
    std::vector<std::string> listNodes();
    void displayNodeStatus();

    // File operations
    bool writeFile(const std::string &filename, const std::string &content);
    bool writeFileToNode(const std::string &nodeId, const std::string &filename, const std::string &content);
    std::string readFile(const std::string &filename);
    bool deleteFile(const std::string &filename);
    std::vector<std::string> listAllFiles();

private:
    std::vector<std::unique_ptr<StorageNode>> nodes;
    int maxRetries;

    // Helper methods
    bool isValidPath(const std::string &path) const;
    std::string normalizeFilepath(const std::string &path) const;
    StorageNode *selectOptimalNode() const;
    void validateNodeExists(const std::string &nodeId) const;
    std::string formatSize(size_t bytes) const;

    // Metadata management
    struct FileMetadata
    {
        std::map<std::string, std::string> attributes;
    };
    std::map<std::string, FileMetadata> fileMetadata;
};

#endif // FILE_SYSTEM_MANAGER_H
