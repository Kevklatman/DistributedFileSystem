#ifndef STORAGE_NODE_H
#define STORAGE_NODE_H

#include <string>
#include <vector>
#include <map>

class StorageNode {
private:
    std::string nodeId;
    std::string basePath;
    std::map<std::string, std::string> fileMap; // filename -> filepath

public:
    StorageNode(const std::string& id, const std::string& path);
    
    bool storeFile(const std::string& filename, const std::string& content);
    std::string retrieveFile(const std::string& filename);
    bool deleteFile(const std::string& filename);
    std::vector<std::string> listFiles();
};

#endif