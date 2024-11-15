#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "manager/FileSystemManager.h"

namespace py = pybind11;

PYBIND11_MODULE(fs_manager, m) {
    py::class_<FileSystemManager>(m, "FileSystemManager")
        .def(py::init<>())
        .def("writeFile", &FileSystemManager::writeFile)
        .def("readFile", &FileSystemManager::readFile)
        .def("deleteFile", &FileSystemManager::deleteFile)
        .def("listAllFiles", &FileSystemManager::listAllFiles)
        .def("createDirectory", &FileSystemManager::createDirectory)
        .def("deleteDirectory", &FileSystemManager::deleteDirectory);
}
