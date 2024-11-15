#include "storage/StorageNode.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/statvfs.h>

StorageNode::StorageNode(const std::string &nodeId, const std::string &basePath)
    : nodeId(nodeId), basePath(basePath)
{
    if (!ensureDirectoryExists())
    {
        throw std::runtime_error("Failed to create or access storage directory: " + basePath);
    }
}

bool StorageNode::storeFile(const std::string &filename, const std::string &content)
{
    try
    {
        std::string fullPath = getFullPath(filename);
        std::ofstream file(fullPath);
        if (file.is_open())
        {
            file << content;
            file.close();
            fileMap[filename] = fullPath;
            return true;
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error storing file: " << e.what() << std::endl;
    }
    return false;
}

std::string StorageNode::retrieveFile(const std::string &filename)
{
    auto it = fileMap.find(filename);
    if (it != fileMap.end())
    {
        try
        {
            std::ifstream file(it->second);
            if (file.is_open())
            {
                return std::string((std::istreambuf_iterator<char>(file)),
                                   std::istreambuf_iterator<char>());
            }
        }
        catch (const std::exception &e)
        {
            std::cerr << "Error retrieving file: " << e.what() << std::endl;
        }
    }
    return "";
}

bool StorageNode::deleteFile(const std::string &filename)
{
    auto it = fileMap.find(filename);
    if (it != fileMap.end())
    {
        try
        {
            if (std::filesystem::remove(it->second))
            {
                fileMap.erase(it);
                return true;
            }
        }
        catch (const std::exception &e)
        {
            std::cerr << "Error deleting file: " << e.what() << std::endl;
        }
    }
    return false;
}

std::vector<std::string> StorageNode::listFiles()
{
    std::vector<std::string> files;
    for (const auto &pair : fileMap)
    {
        files.push_back(pair.first);
    }
    return files;
}

size_t StorageNode::getFileCount() const
{
    return fileMap.size();
}

size_t StorageNode::getTotalSpaceUsed() const
{
    size_t totalSize = 0;
    try
    {
        for (const auto &entry : std::filesystem::directory_iterator(basePath))
        {
            totalSize += std::filesystem::file_size(entry.path());
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error calculating space: " << e.what() << std::endl;
    }
    return totalSize;
}

double StorageNode::getDiskUsagePercentage() const
{
    try
    {
        struct statvfs stat;
        if (statvfs(basePath.c_str(), &stat) == 0)
        {
            double totalSpace = static_cast<double>(stat.f_blocks) * stat.f_frsize;
            double availSpace = static_cast<double>(stat.f_bavail) * stat.f_frsize;
            double usedSpace = totalSpace - availSpace;
            return (usedSpace / totalSpace) * 100.0;
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error calculating disk usage: " << e.what() << std::endl;
    }
    return 0.0;
}

bool StorageNode::ensureDirectoryExists() const
{
    try
    {
        if (!std::filesystem::exists(basePath))
        {
            return std::filesystem::create_directories(basePath);
        }
        return std::filesystem::is_directory(basePath);
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error creating directory: " << e.what() << std::endl;
        return false;
    }
}

std::string StorageNode::getFullPath(const std::string &filename) const
{
    return basePath + "/" + filename;
}
