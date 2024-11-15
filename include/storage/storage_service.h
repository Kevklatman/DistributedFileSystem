// storage_service.h
#pragma once

#include <grpcpp/grpcpp.h>
#include "storage.grpc.pb.h"
#include "storage/StorageNode.h"
#include <memory>
#include <string>

namespace storage
{

    class StorageServiceImpl final : public StorageService::Service
    {
    public:
        explicit StorageServiceImpl(std::shared_ptr<StorageNode> node);

        grpc::Status StoreChunk(grpc::ServerContext *context,
                                const StoreChunkRequest *request,
                                StoreChunkResponse *response) override;

        grpc::Status RetrieveChunk(grpc::ServerContext *context,
                                   const RetrieveChunkRequest *request,
                                   RetrieveChunkResponse *response) override;

        grpc::Status DeleteFile(grpc::ServerContext *context,
                                const DeleteFileRequest *request,
                                DeleteFileResponse *response) override;

        grpc::Status ListFiles(grpc::ServerContext *context,
                               const ListFilesRequest *request,
                               ListFilesResponse *response) override;

        grpc::Status HealthCheck(grpc::ServerContext *context,
                                 const HealthCheckRequest *request,
                                 HealthCheckResponse *response) override;

    private:
        std::shared_ptr<StorageNode> node_;
        std::string computeChecksum(const std::string &data);
        bool validateRequest(const StoreChunkRequest *request, std::string &error);
        double measureLatency();
    };

} // namespace storage
