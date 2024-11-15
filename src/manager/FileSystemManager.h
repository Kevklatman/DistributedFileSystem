#ifndef FILE_SYSTEM_MANAGER_H
#define FILE_SYSTEM_MANAGER_H

#include <vector>
#include <memory>
#include "../storage/StorageNode.h"

class FileSystemManager {
public:
    FileSystemManager();
    void addStorageNode(const std::string& nodeId, const std::string& path);
    bool writeFile(const std::string& filename, const std::string& content);
    bool writeFileToNode(const std::string& nodeId, const std::string& filename, const std::string& content); // New method
    std::string readFile(const std::string& filename);
    bool deleteFile(const std::string& filename);
    std::vector<std::string> listAllFiles();
    std::vector<std::string> listNodes(); // New method to list available nodes
private:
    std::vector<std::unique_ptr<StorageNode>> nodes;
};

#endif