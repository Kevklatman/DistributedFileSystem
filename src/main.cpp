#include <iostream>
#include <string>
#include "manager/FileSystemManager.h"

void printMenu() {
    std::cout << "\n=== Distributed File System ===\n"
              << "1. Write file\n"
              << "2. Read file\n"
              << "3. List files\n"
              << "4. Delete file\n"
              << "5. Add storage node\n"
              << "6. Exit\n"
              << "Choose command (1-6): ";
}

int main() {
    std::cout << "Distributed File System Starting...\n";
    
    FileSystemManager fsManager;
    
    // Initialize with default storage nodes
    fsManager.addStorageNode("node1", "./storage1");
    fsManager.addStorageNode("node2", "./storage2");
    
    while (true) {
        printMenu();
        
        int choice;
        std::cin >> choice;
        std::cin.ignore(); // Clear newline from input buffer

        switch (choice) {
            case 1: {
                std::string filename, content;
                std::cout << "Enter filename: ";
                std::getline(std::cin, filename);
                std::cout << "Enter content (end with Enter): ";
                std::getline(std::cin, content);
                
                if (fsManager.writeFile(filename, content)) {
                    std::cout << "✅ File written successfully\n";
                } else {
                    std::cout << "❌ Failed to write file\n";
                }
                break;
            }
            
            case 2: {
                std::string filename;
                std::cout << "Enter filename to read: ";
                std::getline(std::cin, filename);
                
                std::string content = fsManager.readFile(filename);
                if (!content.empty()) {
                    std::cout << "\n=== File Content ===\n" << content << "\n=================\n";
                } else {
                    std::cout << "❌ File not found or empty\n";
                }
                break;
            }
            
            case 3: {
                auto files = fsManager.listAllFiles();
                if (files.empty()) {
                    std::cout << "No files stored in the system\n";
                } else {
                    std::cout << "\n=== Stored Files ===\n";
                    for (const auto& file : files) {
                        std::cout << "📄 " << file << "\n";
                    }
                    std::cout << "==================\n";
                }
                break;
            }
            
            case 4: {
                std::string filename;
                std::cout << "Enter filename to delete: ";
                std::getline(std::cin, filename);
                
                if (fsManager.deleteFile(filename)) {
                    std::cout << "✅ File deleted successfully\n";
                } else {
                    std::cout << "❌ Failed to delete file\n";
                }
                break;
            }
            
            case 5: {
                std::string nodeId, path;
                std::cout << "Enter node ID: ";
                std::getline(std::cin, nodeId);
                std::cout << "Enter storage path: ";
                std::getline(std::cin, path);
                
                fsManager.addStorageNode(nodeId, path);
                std::cout << "✅ Storage node added\n";
                break;
            }
            
            case 6: {
                std::cout << "Shutting down filesystem...\n";
                return 0;
            }
            
            default:
                std::cout << "❌ Invalid choice. Please select 1-6\n";
        }
    }
    
    return 0;
}