class FileSystemManager:
    def __init__(self):
        self.files = {}
        self.directories = set()

    def writeFile(self, filename, content):
        self.files[filename] = content
        return True

    def readFile(self, filename):
        return self.files.get(filename, None)

    def deleteFile(self, filename):
        if filename in self.files:
            del self.files[filename]
            return True
        return False

    def listAllFiles(self):
        return list(self.files.keys())

    def createDirectory(self, path):
        self.directories.add(path)
        return True

    def deleteDirectory(self, path):
        if path in self.directories:
            self.directories.remove(path)
            # Remove all files in this directory
            files_to_delete = [f for f in self.files if f.startswith(path)]
            for f in files_to_delete:
                del self.files[f]
            return True
        return False
