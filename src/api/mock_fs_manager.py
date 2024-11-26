class FileSystemManager:
    def __init__(self):
        self.files = {}
        self.directories = set()
        self.directories.add("/")  # Root directory always exists

    def _normalize_path(self, path):
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path
        # Remove trailing slash except for root
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return path

    def writeFile(self, filename, content):
        filename = self._normalize_path(filename)
        # Ensure parent directory exists
        parent_dir = "/".join(filename.split("/")[:-1])
        if parent_dir and parent_dir not in self.directories:
            return False
        self.files[filename] = content
        return True

    def readFile(self, filename):
        filename = self._normalize_path(filename)
        return self.files.get(filename)

    def deleteFile(self, filename):
        filename = self._normalize_path(filename)
        if filename in self.files:
            del self.files[filename]
            return True
        return False

    def listAllFiles(self):
        return list(self.files.keys())

    def createDirectory(self, path):
        path = self._normalize_path(path)
        # Create parent directories if they don't exist
        parts = path.split("/")
        current_path = ""
        for part in parts:
            if not part:
                continue
            current_path += "/" + part
            self.directories.add(current_path)
        return True

    def deleteDirectory(self, path):
        path = self._normalize_path(path)
        if path in self.directories:
            # Remove this directory and all subdirectories
            dirs_to_delete = [d for d in self.directories if d.startswith(path)]
            for d in dirs_to_delete:
                self.directories.remove(d)
            # Remove all files in this directory and subdirectories
            files_to_delete = [f for f in self.files if f.startswith(path)]
            for f in files_to_delete:
                del self.files[f]
            return True
        return False

    def listDirectory(self, path):
        path = self._normalize_path(path)
        if path not in self.directories:
            return None
        files = [f for f in self.files if f.startswith(path + "/")]
        subdirs = [
            d
            for d in self.directories
            if d.startswith(path + "/") and d.count("/") == path.count("/") + 1
        ]
        return {"files": files, "directories": subdirs}
