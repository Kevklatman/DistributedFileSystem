// storage_server.cpp
#include <grpcpp/grpcpp.h>
#include "storage_service.h"
#include <memory>
#include <string>
#include <iostream>

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        std::cerr << "Usage: " << argv[0] << " <port> <storage_path>" << std::endl;
        return 1;
    }

    std::string server_address = "0.0.0.0:" + std::string(argv[1]);
    std::string storage_path = argv[2];

    // Create storage node
    auto storage_node = std::make_shared<StorageNode>("node1", storage_path);

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
