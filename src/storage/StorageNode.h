#include <string>
#include <vector>
#include <map>
#include <filesystem>

class StorageNode {
public:
    StorageNode(const std::string& id, const std::string& path);
    bool storeFile(const std::string& filename, const std::string& content);
    std::string retrieveFile(const std::string& filename);
    bool deleteFile(const std::string& filename);
    std::vector<std::string> listFiles();
    std::string getNodeId() const { return nodeId; }
    
    // New methods for status information
    size_t getFileCount() const { return fileMap.size(); }
    size_t getTotalSpaceUsed() const;
    std::string getBasePath() const { return basePath; }
    double getDiskUsagePercentage() const;

private:
    std::string nodeId;
    std::string basePath;
    std::map<std::string, std::string> fileMap;
};