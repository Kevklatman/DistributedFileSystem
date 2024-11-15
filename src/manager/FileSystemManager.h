#ifndef FILE_SYSTEM_MANAGER_H
#define FILE_SYSTEM_MANAGER_H

#include <vector>
#include <memory>
#include "../storage/StorageNode.h"

class FileSystemManager {

        FileSystemManager();

    FileSystemManager(int retries);
public:
    // Search features
    std::vector<std::string> searchByName(const std::string& pattern);
    std::vector<std::string> searchByContent(const std::string& pattern);
    std::vector<std::string> searchByMetadata(const std::string& key, const std::string& value);
    
    // Core file operations
    bool writeFile(const std::string& filename, const std::string& content);
    bool writeFileToNode(const std::string& nodeId, const std::string& filename, const std::string& content);
    std::string readFile(const std::string& filename);
    bool deleteFile(const std::string& filename);
    std::vector<std::string> listAllFiles();
    
    // Node management
    void addStorageNode(const std::string& nodeId, const std::string& path);
    std::vector<std::string> listNodes();
    void displayNodeStatus();



    // Organization features
    bool createDirectory(const std::string& dirPath);
    bool moveToDirectory(const std::string& filename, const std::string& dirPath);
    std::vector<std::string> listDirectory(const std::string& dirPath);
    bool addMetadata(const std::string& filename, const std::string& key, const std::string& value);
    std::map<std::string, std::string> getMetadata(const std::string& filename);

private:
    // Storage nodes
    std::vector<std::unique_ptr<StorageNode>> nodes;
    std::shared_mutex metadataMutex;

    // Metadata storage
    struct FileMetadata {
        std::map<std::string, std::string> attributes;
        std::string directory;
    };
    std::map<std::string, FileMetadata> fileMetadata;

    // Helper methods
    bool isValidDirectory(const std::string& dirPath) const;
    bool isFileCompressed(const std::string& filename);
    std::string compressContent(const std::string& content);
    std::string decompressContent(const std::string& compressed);
    std::string formatSize(size_t bytes) const;
    bool isValidPath(const std::string& path) const;
    std::string normalizeFilepath(const std::string& path) const;
    StorageNode* selectOptimalNode() const;
    void validateNodeExists(const std::string& nodeId) const;

    // File operations
    bool replicateFile(const std::string& filename, int copies);
    bool moveFile(const std::string& filename, 
                 const std::string& sourceNode, 
                 const std::string& targetNode);
    bool compressFile(const std::string& filename);
    bool decompressFile(const std::string& filename);
        int maxRetries;

};

#endif