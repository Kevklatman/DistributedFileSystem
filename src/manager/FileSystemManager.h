// FileSystemManager.h
#ifndef FILE_SYSTEM_MANAGER_H
#define FILE_SYSTEM_MANAGER_H

#include <vector>
#include <memory>
#include <mutex>
#include <map>
#include <queue>
#include <future>
#include "storage.grpc.pb.h"
#include "zookeeper/zookeeper.h"
#include "StorageNode.h"

class FileSystemManager
{
public:
    struct ClusterConfig
    {
        std::vector<std::string> seedNodes;
        std::string zookeeperConnection;
        int replicationFactor;
        bool autoFailover;
        std::string consistencyLevel; // "strong", "eventual"
        int quorumSize;
        bool enableAutoRebalancing;
    };

    FileSystemManager(const ClusterConfig &config);
    ~FileSystemManager();

    // Node management
    bool addStorageNode(const std::string &hostname, int port,
                        const StorageNode::StorageConfig &storageConfig);
    bool removeStorageNode(const std::string &nodeId, bool graceful = true);
    std::vector<std::string> listNodes();

    // Cluster operations
    bool joinCluster(const std::string &existingNodeAddress);
    bool leaveCluster(bool graceful = true);
    bool isClusterHealthy() const;

    // File operations with network awareness
    bool writeFile(const std::string &filename, const std::vector<uint8_t> &data);
    std::vector<uint8_t> readFile(const std::string &filename);
    bool deleteFile(const std::string &filename);
    std::vector<std::string> listFiles();

    // Advanced cluster operations
    void rebalanceCluster();
    void updateReplicationFactor(int newFactor);
    bool performFailover(const std::string &failedNodeId);

    // Monitoring and diagnostics
    struct ClusterStats
    {
        size_t totalNodes;
        size_t healthyNodes;
        double avgLatencyMS;
        size_t totalStorageGB;
        size_t usedStorageGB;
        int activeOperations;
        std::map<std::string, StorageNode::NetworkStats> nodeStats;
    };

    ClusterStats getClusterStats() const;
    bool validateClusterHealth();

private:
    // Cluster management
    struct ClusterState
    {
        std::map<std::string, std::shared_ptr<StorageNode>> nodes;
        std::string leaderId;
        bool isLeader;
        std::vector<std::string> partitionMap;
        int currentTerm;
    };

    ClusterConfig config;
    ClusterState state;
    std::mutex stateMutex;
    zhandle_t *zkHandle;

    // Leader election
    void initializeZookeeper();
    void handleLeaderElection();
    bool becomeLeader();
    void stepDown();

    // Node coordination
    bool registerWithCluster(std::shared_ptr<StorageNode> node);
    void updatePartitionMap();
    std::vector<std::shared_ptr<StorageNode>> selectNodesForOperation(
        const std::string &key, int count);

    // Data distribution
    struct DataPlacement
    {
        std::vector<std::string> primaryNodes;
        std::vector<std::string> replicaNodes;
    };

    DataPlacement calculateDataPlacement(const std::string &filename);
    bool ensureReplication(const std::string &filename, const std::vector<uint8_t> &data);
    bool validateQuorum(const std::string &operation) const;

    // Health checking
    void startHealthMonitor();
    void monitorClusterHealth();
    void handleNodeFailure(const std::string &nodeId);

    // Utility functions
    std::string generateNodeId() const;
    bool isNodeHealthy(const std::shared_ptr<StorageNode> &node) const;
    void logClusterEvent(const std::string &event, const std::string &details);
};

// FileSystemManager.cpp

#include "FileSystemManager.h"
#include <chrono>
#include <random>
#include <thread>

FileSystemManager::FileSystemManager(const ClusterConfig &config) : config(config)
{
    initializeZookeeper();
    startHealthMonitor();
}

void FileSystemManager::initializeZookeeper()
{
    zkHandle = zookeeper_init(config.zookeeperConnection.c_str(), [](zhandle_t *, int, int, const char *, void *) {}, 30000, nullptr, nullptr, 0);

    if (!zkHandle)
    {
        throw std::runtime_error("Failed to initialize ZooKeeper");
    }

    // Create required ZNodes
    zoo_create(zkHandle, "/dfs", nullptr, -1, &ZOO_OPEN_ACL_UNSAFE,
               0, nullptr, 0);
    zoo_create(zkHandle, "/dfs/nodes", nullptr, -1, &ZOO_OPEN_ACL_UNSAFE,
               0, nullptr, 0);
    zoo_create(zkHandle, "/dfs/leader", nullptr, -1, &ZOO_OPEN_ACL_UNSAFE,
               ZOO_EPHEMERAL, nullptr, 0);
}

bool FileSystemManager::addStorageNode(const std::string &hostname, int port,
                                       const StorageNode::StorageConfig &storageConfig)
{
    std::string nodeId = generateNodeId();

    // Create and initialize the storage node
    auto node = std::make_shared<StorageNode>(nodeId, hostname, port);
    StorageNode::NetworkConfig netConfig;
    netConfig.hostname = hostname;
    netConfig.port = port;
    netConfig.useTLS = true;

    if (!node->initialize(netConfig, storageConfig))
    {
        return false;
    }

    // Register node with ZooKeeper
    std::string nodePath = "/dfs/nodes/" + nodeId;
    std::string nodeData = hostname + ":" + std::to_string(port);

    int result = zoo_create(zkHandle, nodePath.c_str(), nodeData.c_str(),
                            nodeData.length(), &ZOO_OPEN_ACL_UNSAFE,
                            ZOO_EPHEMERAL, nullptr, 0);

    if (result != ZOK)
    {
        return false;
    }

    // Add to local state
    {
        std::lock_guard<std::mutex> lock(stateMutex);
        state.nodes[nodeId] = node;
    }

    // Update partition map
    updatePartitionMap();

    // Start rebalancing if enabled
    if (config.enableAutoRebalancing)
    {
        rebalanceCluster();
    }

    return true;
}

bool FileSystemManager::writeFile(const std::string &filename,
                                  const std::vector<uint8_t> &data)
{
    // Calculate data placement
    auto placement = calculateDataPlacement(filename);

    if (placement.primaryNodes.empty())
    {
        return false;
    }

    // Write to primary node
    auto primaryNode = state.nodes[placement.primaryNodes[0]];
    if (!primaryNode->storeFile(filename, data))
    {
        return false;
    }

    // Ensure replication
    if (!ensureReplication(filename, data))
    {
        // Handle replication failure
        std::cerr << "Warning: Replication incomplete for " << filename << std::endl;
    }

    return true;
}

std::vector<uint8_t> FileSystemManager::readFile(const std::string &filename)
{
    auto placement = calculateDataPlacement(filename);

    // Try nodes in order until successful read
    for (const auto &nodeId : placement.primaryNodes)
    {
        auto node = state.nodes[nodeId];
        if (auto data = node->retrieveFile(filename); !data.empty())
        {
            return data;
        }
    }

    // Try replica nodes if primary failed
    for (const auto &nodeId : placement.replicaNodes)
    {
        auto node = state.nodes[nodeId];
        if (auto data = node->retrieveFile(filename); !data.empty())
        {
            return data;
        }
    }

    return std::vector<uint8_t>();
}

void FileSystemManager::monitorClusterHealth()
{
    while (true)
    {
        std::vector<std::string> unhealthyNodes;

        {
            std::lock_guard<std::mutex> lock(stateMutex);
            for (const auto &[nodeId, node] : state.nodes)
            {
                if (!isNodeHealthy(node))
                {
                    unhealthyNodes.push_back(nodeId);
                }
            }
        }

        // Handle unhealthy nodes
        for (const auto &nodeId : unhealthyNodes)
        {
            handleNodeFailure(nodeId);
        }

        // Update cluster stats
        auto stats = getClusterStats();
        if (stats.healthyNodes < config.quorumSize)
        {
            logClusterEvent("CRITICAL", "Cluster quorum lost");
            // Initiate emergency procedures
        }

        std::this_thread::sleep_for(std::chrono::seconds(30));
    }
}

FileSystemManager::ClusterStats FileSystemManager::getClusterStats() const
{
    ClusterStats stats;
    stats.totalNodes = state.nodes.size();
    stats.healthyNodes = 0;
    stats.avgLatencyMS = 0;
    stats.totalStorageGB = 0;
    stats.usedStorageGB = 0;

    for (const auto &[nodeId, node] : state.nodes)
    {
        auto nodeStats = node->getNetworkStats();
        stats.nodeStats[nodeId] = nodeStats;

        if (nodeStats.status == "healthy")
        {
            stats.healthyNodes++;
        }

        stats.avgLatencyMS += nodeStats.latencyMS;
        // Add other stat calculations
    }

    if (!state.nodes.empty())
    {
        stats.avgLatencyMS /= state.nodes.size();
    }

    return stats;
}

void FileSystemManager::rebalanceCluster()
{
    std::lock_guard<std::mutex> lock(stateMutex);

    // Calculate ideal distribution
    size_t totalStorage = 0;
    for (const auto &[_, node] : state.nodes)
    {
        auto stats = node->getNetworkStats();
        totalStorage += stats.bytesTransferred;
    }

    size_t targetPerNode = totalStorage / state.nodes.size();

    // Identify overloaded and underloaded nodes
    std::vector<std::string> overloadedNodes, underloadedNodes;
    for (const auto &[nodeId, node] : state.nodes)
    {
        auto stats = node->getNetworkStats();
        if (stats.bytesTransferred > targetPerNode * 1.1)
        {
            overloadedNodes.push_back(nodeId);
        }
        else if (stats.bytesTransferred < targetPerNode * 0.9)
        {
            underloadedNodes.push_back(nodeId);
        }
    }

    // Move data to balance the load
    for (const auto &sourceId : overloadedNodes)
    {
        for (const auto &targetId : underloadedNodes)
        {
            // Calculate amount to move
            auto sourceStats = state.nodes[sourceId]->getNetworkStats();
            auto targetStats = state.nodes[targetId]->getNetworkStats();

            size_t amountToMove = (sourceStats.bytesTransferred - targetPerNode) / 2;

            // Move data
            // This would involve selecting files to move and transferring them
            // Implementation details would depend on specific requirements
        }
    }
}

bool FileSystemManager::performFailover(const std::string &failedNodeId)
{
    std::lock_guard<std::mutex> lock(stateMutex);

    auto it = state.nodes.find(failedNodeId);
    if (it == state.nodes.end())
    {
        return false;
    }

    // Remove failed node
    state.nodes.erase(it);

    // Update ZooKeeper
    std::string nodePath = "/dfs/nodes/" + failedNodeId;
    zoo_delete(zkHandle, nodePath.c_str(), -1);

    // Trigger replication for affected data
    updatePartitionMap();

    // Log the event
    logClusterEvent("FAILOVER", "Node " + failedNodeId + " failed over");

    return true;
}
