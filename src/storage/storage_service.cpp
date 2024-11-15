// storage_service.cpp
#include "storage_service.h"
#include <openssl/md5.h>
#include <chrono>
#include <sstream>
#include <iomanip>

namespace storage
{

    StorageServiceImpl::StorageServiceImpl(std::shared_ptr<StorageNode> node)
        : node_(node) {}

    grpc::Status StorageServiceImpl::StoreChunk(grpc::ServerContext *context,
                                                const StoreChunkRequest *request,
                                                StoreChunkResponse *response)
    {
        std::string error;
        if (!validateRequest(request, error))
        {
            response->set_success(false);
            response->set_message(error);
            return grpc::Status(grpc::StatusCode::INVALID_ARGUMENT, error);
        }

        // Verify checksum if provided
        if (!request->checksum().empty())
        {
            std::string computed = computeChecksum(request->data());
            if (computed != request->checksum())
            {
                response->set_success(false);
                response->set_message("Checksum verification failed");
                return grpc::Status(grpc::StatusCode::DATA_LOSS, "Checksum mismatch");
            }
        }

        // Create filename with chunk number if needed
        std::string filename = request->filename();
        if (request->chunk_number() > 0)
        {
            filename += ".chunk" + std::to_string(request->chunk_number());
        }

        try
        {
            bool success = node_->storeFile(filename, request->data());
            response->set_success(success);
            response->set_message(success ? "Chunk stored successfully" : "Failed to store chunk");
            return success ? grpc::Status::OK : grpc::Status(grpc::StatusCode::INTERNAL, "Storage operation failed");
        }
        catch (const std::exception &e)
        {
            response->set_success(false);
            response->set_message(e.what());
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

    grpc::Status StorageServiceImpl::RetrieveChunk(grpc::ServerContext *context,
                                                   const RetrieveChunkRequest *request,
                                                   RetrieveChunkResponse *response)
    {
        if (request->filename().empty())
        {
            return grpc::Status(grpc::StatusCode::INVALID_ARGUMENT, "Filename is required");
        }

        std::string filename = request->filename();
        if (request->chunk_number() > 0)
        {
            filename += ".chunk" + std::to_string(request->chunk_number());
        }

        try
        {
            std::string data = node_->retrieveFile(filename);
            if (data.empty())
            {
                response->set_success(false);
                response->set_message("Chunk not found");
                return grpc::Status(grpc::StatusCode::NOT_FOUND, "Chunk not found");
            }

            response->set_data(data);
            response->set_success(true);
            response->set_checksum(computeChecksum(data));
            response->set_message("Chunk retrieved successfully");
            return grpc::Status::OK;
        }
        catch (const std::exception &e)
        {
            response->set_success(false);
            response->set_message(e.what());
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

    grpc::Status StorageServiceImpl::DeleteFile(grpc::ServerContext *context,
                                                const DeleteFileRequest *request,
                                                DeleteFileResponse *response)
    {
        if (request->filename().empty())
        {
            return grpc::Status(grpc::StatusCode::INVALID_ARGUMENT, "Filename is required");
        }

        try
        {
            bool success = node_->deleteFile(request->filename());
            response->set_success(success);
            response->set_message(success ? "File deleted successfully" : "File not found");
            return grpc::Status::OK;
        }
        catch (const std::exception &e)
        {
            response->set_success(false);
            response->set_message(e.what());
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

    grpc::Status StorageServiceImpl::ListFiles(grpc::ServerContext *context,
                                               const ListFilesRequest *request,
                                               ListFilesResponse *response)
    {
        try
        {
            auto files = node_->listFiles();
            for (const auto &file : files)
            {
                response->add_filenames(file);
            }
            return grpc::Status::OK;
        }
        catch (const std::exception &e)
        {
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

    grpc::Status StorageServiceImpl::HealthCheck(grpc::ServerContext *context,
                                                 const HealthCheckRequest *request,
                                                 HealthCheckResponse *response)
    {
        try
        {
            response->set_healthy(true);
            response->set_latency_ms(measureLatency());

            double disk_usage = node_->getDiskUsagePercentage();
            if (disk_usage > 90.0)
            {
                response->set_status("WARNING: High disk usage");
                response->set_healthy(false);
            }
            else
            {
                response->set_status("OK");
            }

            return grpc::Status::OK;
        }
        catch (const std::exception &e)
        {
            response->set_healthy(false);
            response->set_status(std::string("ERROR: ") + e.what());
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

    // Private helper methods
    std::string StorageServiceImpl::computeChecksum(const std::string &data)
    {
        unsigned char result[MD5_DIGEST_LENGTH];
        MD5(reinterpret_cast<const unsigned char *>(data.c_str()), data.length(), result);

        std::stringstream ss;
        for (int i = 0; i < MD5_DIGEST_LENGTH; i++)
        {
            ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(result[i]);
        }
        return ss.str();
    }

    bool StorageServiceImpl::validateRequest(const StoreChunkRequest *request, std::string &error)
    {
        if (request->filename().empty())
        {
            error = "Filename is required";
            return false;
        }
        if (request->data().empty())
        {
            error = "Data is required";
            return false;
        }
        if (request->chunk_number() < 0)
        {
            error = "Chunk number must be non-negative";
            return false;
        }
        return true;
    }

    double StorageServiceImpl::measureLatency()
    {
        auto start = std::chrono::high_resolution_clock::now();
        node_->listFiles(); // Simple operation to measure latency
        auto end = std::chrono::high_resolution_clock::now();

        std::chrono::duration<double, std::milli> duration = end - start;
        return duration.count();
    }

} // namespace storage
