from flask import Flask, request, jsonify
import os
from manager import FileSystemManager  # Import your distributed file system manager
# Ensure that the storage_manager.py file is in the correct directory
# and the FileSystemManager class is correctly defined in it.
try:
    from manager import FileSystemManager  # Import your distributed file system manager
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from manager import FileSystemManager

app = Flask(__name__)
fs_manager = FileSystemManager()

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    filename = file.filename
    content = file.read()
    success = fs_manager.writeFile(filename, content)
    if success:
        return jsonify({"message": "File uploaded successfully"}), 200
    else:
        return jsonify({"message": "Failed to upload file"}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    content = fs_manager.readFile(filename)
    if content:
        return content, 200
    else:
        return jsonify({"message": "File not found"}), 404

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    success = fs_manager.deleteFile(filename)
    if success:
        return jsonify({"message": "File deleted successfully"}), 200
    else:
        return jsonify({"message": "Failed to delete file"}), 500

@app.route('/list', methods=['GET'])
def list_files():
    files = fs_manager.listAllFiles()
    return jsonify(files), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
