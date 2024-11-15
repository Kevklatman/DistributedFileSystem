#ifndef FILE_SYSTEM_MANAGER_H
#define FILE_SYSTEM_MANAGER_H

#include <string>
#include <vector>
#include <memory>
#include <map>
#include "storage/StorageNode.h"

// Result structure for write operations
struct WriteResult
{
    bool success;
    std::string message;
    std::string nodeId;
    size_t bytesWritten;

    WriteResult(bool s = false, const std::string &msg = "",
                const std::string &node = "", size_t bytes = 0)
        : success(s), message(msg), nodeId(node), bytesWritten(bytes) {}
};

class FileSystemManager
{
public:
    FileSystemManager();
    explicit FileSystemManager(int maxRetries);
    ~FileSystemManager() = default;

    // Node management
    void addStorageNode(const std::string &nodeId, const std::string &path);
    std::vector<std::string> listNodes();
    void displayNodeStatus();
    StorageNode *getNode(const std::string &nodeId);
    void removeNode(const std::string &nodeId);

    // File operations - Basic
    bool writeFile(const std::string &filename, const std::string &content);
    std::string readFile(const std::string &filename);
    bool deleteFile(const std::string &filename);
    std::vector<std::string> listAllFiles();

    // File operations - Advanced
    WriteResult writeFileToNode(const std::string &nodeId,
                                const std::string &filename,
                                const std::string &content);

    WriteResult writeFileToNodes(const std::vector<std::string> &nodeIds,
                                 const std::string &filename,
                                 const std::string &content);

    bool replicateFile(const std::string &filename,
                       const std::string &sourceNodeId,
                       const std::string &targetNodeId);

    // Node health and balancing
    double getNodeUsage(const std::string &nodeId) const;
    std::vector<std::string> getOverloadedNodes(double threshold = 80.0) const;
    bool rebalanceNodes();

private:
    std::vector<std::unique_ptr<StorageNode>> nodes;
    int maxRetries;
    size_t maxFileSize;
    bool enableReplication;

    // Helper methods
    bool isValidPath(const std::string &path) const;
    std::string normalizeFilepath(const std::string &path) const;
    StorageNode *selectOptimalNode() const;
    StorageNode *findNode(const std::string &nodeId);
    const StorageNode *findNode(const std::string &nodeId) const;
    void validateNodeExists(const std::string &nodeId) const;
    std::string formatSize(size_t bytes) const;
    bool validateWrite(const std::string &nodeId,
                       const std::string &filename,
                       size_t contentSize) const;

    // Metadata management
    struct FileMetadata
    {
        std::map<std::string, std::string> attributes;
        std::vector<std::string> nodeLocations;
        size_t size;
        time_t lastModified;
        int replicationCount;

        FileMetadata() : size(0), lastModified(0), replicationCount(0) {}
    };

    std::map<std::string, FileMetadata> fileMetadata;

    // Internal metadata operations
    void updateFileMetadata(const std::string &filename,
                            const std::string &nodeId,
                            size_t size);
    void removeFileMetadata(const std::string &filename,
                            const std::string &nodeId);

    // Configuration settings
    struct Config
    {
        size_t minReplicationFactor = 1;
        size_t maxReplicationFactor = 3;
        double balanceThreshold = 80.0;
        size_t maxRetryAttempts = 3;
        bool autoRebalance = true;
    } config;

    // Error handling
    void logError(const std::string &operation,
                  const std::string &message,
                  const std::string &nodeId = "") const;

    // Node selection strategies
    StorageNode *selectNodeBySpace() const;
    StorageNode *selectNodeByLatency() const;
    StorageNode *selectNodeRoundRobin();

    // Load balancing
    bool needsRebalancing() const;
    std::vector<std::pair<std::string, double>> getNodeUtilization() const;
};

#endif // FILE_SYSTEM_MANAGER_H
