// storage_server.cpp
#include <grpcpp/grpcpp.h>
#include "storage_service.h"
#include <memory>
#include <string>
#include <iostream>
#include <cstdlib>

std::string getNodeId()
{
    char *nodeId = std::getenv("NODE_ID");
    return nodeId ? std::string(nodeId) : "unknown";
}

std::string getPodIP()
{
    char *podIP = std::getenv("POD_IP");
    return podIP ? std::string(podIP) : "0.0.0.0";
}

int main(int argc, char **argv)
{
    std::string server_address;
    std::shared_ptr<StorageNode> storage_node;

    if (argc != 3)
    {
        // Use environment variables (container mode)
        std::string nodeId = getNodeId();
        std::string podIP = getPodIP();
        server_address = podIP + ":50051";
        storage_node = std::make_shared<StorageNode>(nodeId, "/data");
    }
    else
    {
        // Use command line arguments (development mode)
        server_address = "0.0.0.0:" + std::string(argv[1]);
        storage_node = std::make_shared<StorageNode>("node1", argv[2]);
    }

    // Create and start gRPC server
    storage::StorageServiceImpl service(storage_node);
    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    std::unique_ptr<grpc::Server> server(builder.BuildAndStart());
    std::cout << "Server listening on " << server_address << std::endl;
    server->Wait();

    return 0;
}
