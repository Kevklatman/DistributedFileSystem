#include <iostream>
#include <string>
#include "manager/FileSystemManager.h"
#include "storage/StorageNode.h

void printMenu()
{
    std::cout << "\n=== Distributed File System ===\n"
              << "1. Write file (random node)\n"
              << "2. Write file to specific node\n"
              << "3. Read file\n"
              << "4. List files\n"
              << "5. Delete file\n"
              << "6. Add storage node\n"
              << "7. List storage nodes\n"
              << "8. Show node status\n"
              << "9. Exit\n"
              << "Choose command (1-9): ";
}

int main()
{
    std::cout << "Distributed File System Starting...\n";

    FileSystemManager fsManager;

    // Initialize with default storage nodes
    fsManager.addStorageNode("node1", "./storage1");
    fsManager.addStorageNode("node2", "./storage2");

    while (true)
    {
        printMenu();

        int choice;
        std::cin >> choice;
        std::cin.ignore();

        switch (choice)
        {
        case 1:
        {
            std::string filename, content;
            std::cout << "Enter filename: ";
            std::getline(std::cin, filename);
            std::cout << "Enter content (end with Enter): ";
            std::getline(std::cin, content);

            if (fsManager.writeFile(filename, content))
            {
                std::cout << "✅ File written successfully\n";
            }
            else
            {
                std::cout << "❌ Failed to write file\n";
            }
            break;
        }

        case 2:
        {
            std::string nodeId, filename, content;

            // First show available nodes
            std::cout << "Available nodes:\n";
            for (const auto &node : fsManager.listNodes())
            {
                std::cout << "- " << node << "\n";
            }

            std::cout << "Enter node ID: ";
            std::getline(std::cin, nodeId);
            std::cout << "Enter filename: ";
            std::getline(std::cin, filename);
            std::cout << "Enter content (end with Enter): ";
            std::getline(std::cin, content);

            if (fsManager.writeFileToNode(nodeId, filename, content))
            {
                std::cout << "✅ File written successfully to node " << nodeId << "\n";
            }
            else
            {
                std::cout << "❌ Failed to write file to node " << nodeId << "\n";
            }
            break;
        }

        case 3:
        {
            std::string filename;
            std::cout << "Enter filename to read: ";
            std::getline(std::cin, filename);

            std::string content = fsManager.readFile(filename);
            if (!content.empty())
            {
                std::cout << "\n=== File Content ===\n"
                          << content << "\n=================\n";
            }
            else
            {
                std::cout << "❌ File not found or empty\n";
            }
            break;
        }

        case 4:
        {
            auto files = fsManager.listAllFiles();
            if (files.empty())
            {
                std::cout << "No files stored in the system\n";
            }
            break;
        }

        case 5:
        {
            std::string filename;
            std::cout << "Enter filename to delete: ";
            std::getline(std::cin, filename);

            if (fsManager.deleteFile(filename))
            {
                std::cout << "✅ File deleted successfully\n";
            }
            else
            {
                std::cout << "❌ Failed to delete file\n";
            }
            break;
        }

        case 6:
        {
            std::string nodeId, path;
            std::cout << "Enter node ID: ";
            std::getline(std::cin, nodeId);
            std::cout << "Enter storage path: ";
            std::getline(std::cin, path);

            fsManager.addStorageNode(nodeId, path);
            std::cout << "✅ Storage node added\n";
            break;
        }

        case 7:
        {
            std::cout << "\n=== Storage Nodes ===\n";
            for (const auto &node : fsManager.listNodes())
            {
                std::cout << "📁 " << node << "\n";
            }
            break;
        }

        case 8:
        {
            fsManager.displayNodeStatus();
            break;
        }

        case 9:
        {
            std::cout << "Shutting down filesystem...\n";
            return 0;
        }

        default:
            std::cout << "❌ Invalid choice. Please select 1-8\n";
        }
    }

    return 0;
}
