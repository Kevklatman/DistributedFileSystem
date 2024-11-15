#include "manager/FileSystemManager.h"
#include <iostream>
#include <filesystem>
#include <random>
#include <algorithm>
#include <iomanip>
#include <sstream>

FileSystemManager::FileSystemManager() : maxRetries(3) {}
FileSystemManager::FileSystemManager(int retries) : maxRetries(retries) {}

void FileSystemManager::addStorageNode(const std::string &nodeId, const std::string &path)
{
    if (std::find_if(nodes.begin(), nodes.end(),
                     [&nodeId](const auto &node)
                     {
                         return node->getNodeId() == nodeId;
                     }) != nodes.end())
    {
        throw std::runtime_error("Node ID already exists: " + nodeId);
    }

    try
    {
        nodes.push_back(std::make_unique<StorageNode>(nodeId, path));
        std::cout << "Added storage node: " << nodeId << " at path: " << path << std::endl;
    }
    catch (const std::exception &e)
    {
        throw std::runtime_error("Failed to add storage node: " + std::string(e.what()));
    }
}

bool FileSystemManager::writeFile(const std::string &filename, const std::string &content)
{
    if (nodes.empty())
    {
        std::cout << "No storage nodes available" << std::endl;
        return false;
    }

    // Simple round-robin node selection
    static size_t lastIndex = 0;
    lastIndex = (lastIndex + 1) % nodes.size();

    bool success = nodes[lastIndex]->storeFile(filename, content);
    if (success)
    {
        std::cout << "File written to node: " << nodes[lastIndex]->getNodeId() << std::endl;
    }
    return success;
}

std::string FileSystemManager::readFile(const std::string &filename)
{
    for (const auto &node : nodes)
    {
        std::string content = node->retrieveFile(filename);
        if (!content.empty())
        {
            std::cout << "File found in node: " << node->getNodeId() << std::endl;
            return content;
        }
    }
    std::cout << "File not found in any node" << std::endl;
    return "";
}

bool FileSystemManager::deleteFile(const std::string &filename)
{
    bool deletedAny = false;
    for (const auto &node : nodes)
    {
        if (node->deleteFile(filename))
        {
            std::cout << "File deleted from node: " << node->getNodeId() << std::endl;
            deletedAny = true;
        }
    }
    return deletedAny;
}

std::vector<std::string> FileSystemManager::listAllFiles()
{
    std::vector<std::string> allFiles;
    for (const auto &node : nodes)
    {
        std::cout << "\nFiles in node " << node->getNodeId() << ":\n";
        auto nodeFiles = node->listFiles();
        for (const auto &file : nodeFiles)
        {
            std::cout << "- " << file << std::endl;
        }
        allFiles.insert(allFiles.end(), nodeFiles.begin(), nodeFiles.end());
    }
    return allFiles;
}

std::vector<std::string> FileSystemManager::listNodes()
{
    std::vector<std::string> nodeIds;
    for (const auto &node : nodes)
    {
        nodeIds.push_back(node->getNodeId());
    }
    return nodeIds;
}

void FileSystemManager::displayNodeStatus()
{
    for (const auto &node : nodes)
    {
        std::cout << "\nNode ID: " << node->getNodeId() << "\n"
                  << "Base Path: " << node->getBasePath() << "\n"
                  << "File Count: " << node->getFileCount() << "\n"
                  << "Total Space Used: " << formatSize(node->getTotalSpaceUsed()) << "\n"
                  << "Disk Usage: " << std::fixed << std::setprecision(2)
                  << node->getDiskUsagePercentage() << "%\n";
    }
}

WriteResult FileSystemManager::writeFileToNode(const std::string &nodeId,
                                               const std::string &filename,
                                               const std::string &content)
{
    for (const auto &node : nodes)
    {
        if (node->getNodeId() == nodeId)
        {
            bool success = node->storeFile(filename, content);
            if (success)
            {
                return WriteResult(true, "File written successfully", nodeId, content.size());
            }
            return WriteResult(false, "Failed to write to node", nodeId);
        }
    }
    return WriteResult(false, "Node not found", nodeId);
}

WriteResult FileSystemManager::writeFileToNodes(const std::vector<std::string> &nodeIds,
                                                const std::string &filename,
                                                const std::string &content)
{
    if (nodeIds.empty())
    {
        return WriteResult(false, "No target nodes specified");
    }

    std::vector<std::string> successfulNodes;
    std::string errorMessages;

    for (const auto &nodeId : nodeIds)
    {
        auto result = writeFileToNode(nodeId, filename, content);
        if (result.success)
        {
            successfulNodes.push_back(nodeId);
        }
        else
        {
            errorMessages += "Node " + nodeId + ": " + result.message + "\n";
        }
    }

    if (!successfulNodes.empty())
    {
        std::string message = "Written to " + std::to_string(successfulNodes.size()) +
                              " of " + std::to_string(nodeIds.size()) + " nodes";
        if (!errorMessages.empty())
        {
            message += "\nErrors:\n" + errorMessages;
        }
        return WriteResult(true, message, successfulNodes[0], content.size());
    }

    return WriteResult(false, "Failed to write to any nodes:\n" + errorMessages);
}

StorageNode *FileSystemManager::getNode(const std::string &nodeId)
{
    for (const auto &node : nodes)
    {
        if (node->getNodeId() == nodeId)
        {
            return node.get();
        }
    }
    return nullptr;
}

void FileSystemManager::removeNode(const std::string &nodeId)
{
    nodes.erase(
        std::remove_if(nodes.begin(), nodes.end(),
                       [&nodeId](const auto &node)
                       { return node->getNodeId() == nodeId; }),
        nodes.end());
}

double FileSystemManager::getNodeUsage(const std::string &nodeId) const
{
    if (auto node = findNode(nodeId))
    {
        return node->getDiskUsagePercentage();
    }
    throw std::runtime_error("Node not found: " + nodeId);
}

bool FileSystemManager::rebalanceNodes()
{
    return false; // Placeholder implementation
}

StorageNode *FileSystemManager::selectOptimalNode() const
{
    if (nodes.empty())
    {
        return nullptr;
    }
    return nodes.front().get(); // Placeholder implementation
}

StorageNode *FileSystemManager::findNode(const std::string &nodeId)
{
    auto it = std::find_if(nodes.begin(), nodes.end(),
                           [&nodeId](const auto &node)
                           { return node->getNodeId() == nodeId; });
    return it != nodes.end() ? it->get() : nullptr;
}

const StorageNode *FileSystemManager::findNode(const std::string &nodeId) const
{
    auto it = std::find_if(nodes.begin(), nodes.end(),
                           [&nodeId](const auto &node)
                           { return node->getNodeId() == nodeId; });
    return it != nodes.end() ? it->get() : nullptr;
}

void FileSystemManager::validateNodeExists(const std::string &nodeId) const
{
    if (!findNode(nodeId))
    {
        throw std::runtime_error("Node not found: " + nodeId);
    }
}

std::vector<std::string> FileSystemManager::getOverloadedNodes(double threshold) const
{
    std::vector<std::string> overloaded;
    for (const auto &node : nodes)
    {
        if (node->getDiskUsagePercentage() > threshold)
        {
            overloaded.push_back(node->getNodeId());
        }
    }
    return overloaded;
}

std::string FileSystemManager::formatSize(size_t bytes) const
{
    static const char *units[] = {"B", "KB", "MB", "GB", "TB"};
    int unitIndex = 0;
    double size = static_cast<double>(bytes);

    while (size >= 1024.0 && unitIndex < 4)
    {
        size /= 1024.0;
        unitIndex++;
    }

    std::stringstream ss;
    ss << std::fixed << std::setprecision(2) << size << " " << units[unitIndex];
    return ss.str();
}

bool FileSystemManager::isValidPath(const std::string &path) const
{
    return !path.empty() && path[0] == '/' &&
           path.find("..") == std::string::npos;
}

std::string FileSystemManager::normalizeFilepath(const std::string &path) const
{
    std::filesystem::path normalized = std::filesystem::path(path).lexically_normal();
    return normalized.string();
}

bool FileSystemManager::validateWrite(const std::string &nodeId,
                                      const std::string &filename,
                                      size_t contentSize) const
{
    return !nodeId.empty() && !filename.empty();
}
