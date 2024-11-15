// StorageNode.h
#ifndef STORAGE_NODE_H
#define STORAGE_NODE_H

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <grpcpp/grpcpp.h>
#include "storage.grpc.pb.h"

class StorageNode
{
public:
    StorageNode(const std::string &id, const std::string &hostname, int port);

    // Network configuration
    struct NetworkConfig
    {
        std::string hostname;
        int port;
        int maxConnections;
        bool useTLS;
        std::string certificatePath;
        std::string privateKeyPath;
    };

    // Storage configuration
    struct StorageConfig
    {
        std::string mountPoint;
        size_t capacityGB;
        bool useDirectIO;
        std::string storageType; // "SSD", "HDD", "NVMe"
        std::vector<std::string> networkInterfaces;
    };

    // Initialize with network and storage configs
    bool initialize(const NetworkConfig &netConfig, const StorageConfig &storageConfig);

    // Network operations
    bool connect();
    void disconnect();
    bool isConnected() const;

    // Storage operations with network awareness
    bool storeFile(const std::string &filename, const std::vector<uint8_t> &data);
    std::vector<uint8_t> retrieveFile(const std::string &filename);
    bool deleteFile(const std::string &filename);

    // Network health and diagnostics
    struct NetworkStats
    {
        double latencyMS;
        double bandwidthMBps;
        int activeConnections;
        size_t bytesTransferred;
        std::string status;
    };

    NetworkStats getNetworkStats() const;
    bool performHealthCheck();

private:
    std::string nodeId;
    NetworkConfig networkConfig;
    StorageConfig storageConfig;
    std::unique_ptr<storage::StorageService::Stub> stub;
    std::shared_ptr<grpc::Channel> channel;

    // Network-aware storage management
    bool initializeStorage();
    bool initializeNetwork();
    bool setupTLS();
    void monitorNetwork();

    // Internal networking utilities
    bool sendChunk(const std::string &filename, const std::vector<uint8_t> &chunk, int chunkNum);
    std::vector<uint8_t> receiveChunk(const std::string &filename, int chunkNum);
    void handleNetworkError(const std::string &operation);
};

#endif

// storage.proto
syntax = "proto3";

package storage;

service StorageService
{
    rpc StoreChunk(StoreChunkRequest) returns(StoreChunkResponse) {}
    rpc RetrieveChunk(RetrieveChunkRequest) returns(RetrieveChunkResponse) {}
    rpc DeleteFile(DeleteFileRequest) returns(DeleteFileResponse) {}
    rpc HealthCheck(HealthCheckRequest) returns(HealthCheckResponse) {}
}

message StoreChunkRequest
{
    string filename = 1;
    int32 chunk_number = 2;
    bytes data = 3;
    string checksum = 4;
}

message StoreChunkResponse
{
    bool success = 1;
    string message = 2;
}

message RetrieveChunkRequest
{
    string filename = 1;
    int32 chunk_number = 2;
}

message RetrieveChunkResponse
{
    bytes data = 1;
    string checksum = 2;
    bool success = 3;
    string message = 4;
}

message DeleteFileRequest
{
    string filename = 1;
}

message DeleteFileResponse
{
    bool success = 1;
    string message = 2;
}

message HealthCheckRequest
{
    string node_id = 1;
}

message HealthCheckResponse
{
    bool healthy = 1;
    double latency_ms = 2;
    string status = 3;
}

// StorageNode.cpp
#include "StorageNode.h"
#include <grpcpp/grpcpp.h>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <sys/statvfs.h>
#include <thread>
#include <chrono>

StorageNode::StorageNode(const std::string &id, const std::string &hostname, int port)
    : nodeId(id)
{
    networkConfig.hostname = hostname;
    networkConfig.port = port;
}

bool StorageNode::initialize(const NetworkConfig &netConfig, const StorageConfig &storageConfig)
{
    this->networkConfig = netConfig;
    this->storageConfig = storageConfig;

    if (!initializeNetwork())
    {
        std::cerr << "Failed to initialize network for node " << nodeId << std::endl;
        return false;
    }

    if (!initializeStorage())
    {
        std::cerr << "Failed to initialize storage for node " << nodeId << std::endl;
        return false;
    }

    // Start network monitoring in a separate thread
    std::thread([this]()
                { this->monitorNetwork(); })
        .detach();

    return true;
}

bool StorageNode::initializeNetwork()
{
    grpc::ChannelArguments args;
    args.SetMaxReceiveMessageSize(64 * 1024 * 1024); // 64MB
    args.SetMaxSendMessageSize(64 * 1024 * 1024);    // 64MB

    std::string address = networkConfig.hostname + ":" + std::to_string(networkConfig.port);

    if (networkConfig.useTLS)
    {
        if (!setupTLS())
        {
            return false;
        }

        grpc::SslCredentialsOptions ssl_opts;
        ssl_opts.pem_root_certs = "";  // Add root certs
        ssl_opts.pem_private_key = ""; // Add private key
        ssl_opts.pem_cert_chain = "";  // Add cert chain

        channel = grpc::CreateCustomChannel(
            address,
            grpc::SslCredentials(ssl_opts),
            args);
    }
    else
    {
        channel = grpc::CreateCustomChannel(
            address,
            grpc::InsecureChannelCredentials(),
            args);
    }

    stub = storage::StorageService::NewStub(channel);
    return channel->GetState(true) == GRPC_CHANNEL_READY;
}

bool StorageNode::storeFile(const std::string &filename, const std::vector<uint8_t> &data)
{
    const size_t CHUNK_SIZE = 64 * 1024 * 1024; // 64MB chunks
    size_t chunks = (data.size() + CHUNK_SIZE - 1) / CHUNK_SIZE;

    for (size_t i = 0; i < chunks; i++)
    {
        size_t chunkStart = i * CHUNK_SIZE;
        size_t chunkSize = std::min(CHUNK_SIZE, data.size() - chunkStart);
        std::vector<uint8_t> chunk(data.begin() + chunkStart,
                                   data.begin() + chunkStart + chunkSize);

        if (!sendChunk(filename, chunk, i))
        {
            handleNetworkError("Failed to store chunk " + std::to_string(i));
            return false;
        }
    }

    return true;
}

void StorageNode::monitorNetwork()
{
    while (true)
    {
        auto stats = getNetworkStats();

        // Log or alert if network metrics are concerning
        if (stats.latencyMS > 100)
        { // Alert on high latency
            std::cerr << "High latency detected: " << stats.latencyMS << "ms" << std::endl;
        }

        if (stats.activeConnections > networkConfig.maxConnections)
        {
            std::cerr << "Too many connections: " << stats.activeConnections << std::endl;
        }

        // Perform health check
        storage::HealthCheckRequest request;
        request.set_node_id(nodeId);

        storage::HealthCheckResponse response;
        grpc::ClientContext context;

        grpc::Status status = stub->HealthCheck(&context, request, &response);

        if (!status.ok() || !response.healthy())
        {
            handleNetworkError("Health check failed: " + response.status());
        }

        std::this_thread::sleep_for(std::chrono::seconds(60));
    }
}

StorageNode::NetworkStats StorageNode::getNetworkStats() const
{
    NetworkStats stats;

    // Measure latency
    auto start = std::chrono::high_resolution_clock::now();
    storage::HealthCheckRequest request;
    request.set_node_id(nodeId);

    storage::HealthCheckResponse response;
    grpc::ClientContext context;

    grpc::Status status = stub->HealthCheck(&context, request, &response);

    auto end = std::chrono::high_resolution_clock::now();
    stats.latencyMS = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    // Get other metrics
    stats.activeConnections = /* Get from channel stats */;
    stats.bandwidthMBps = /* Calculate from recent transfers */;
    stats.bytesTransferred = /* Get from transfer logs */;
    stats.status = status.ok() ? "healthy" : "unhealthy";

    return stats;
}
