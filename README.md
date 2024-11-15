# Distributed File System

An S3-compatible distributed file system implemented in Python. Supports both local storage and AWS S3 backends.

## Features

- S3-compatible API
- Multiple storage backends (Local and AWS S3)
- Easy switching between backends via environment variables
- Docker support

## API Endpoints

All endpoints follow the S3 API specification:

- `GET /` - List all buckets
- `PUT /<bucket>` - Create a bucket
- `DELETE /<bucket>` - Delete a bucket
- `GET /<bucket>` - List objects in bucket
- `PUT /<bucket>/<key>` - Upload an object
- `GET /<bucket>/<key>` - Download an object
- `DELETE /<bucket>/<key>` - Delete an object

## Setup

1. Clone the repository:
```bash
git clone https://github.com/Kevklatman/DistributedFileSystem.git
cd DistributedFileSystem
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Running

### Local Development
```bash
python -m flask run --host=0.0.0.0 --port=5555
```

### Docker
```bash
docker build -t dfs .
docker run -p 5555:5555 dfs
```

## Configuration

Set the following environment variables in `.env`:

```bash
# Storage backend ('local' or 'aws')
STORAGE_ENV=local

# AWS credentials (if using aws backend)
AWS_ACCESS_KEY=your-key
AWS_SECRET_KEY=your-secret
AWS_REGION=us-east-1

# API settings
API_HOST=0.0.0.0
API_PORT=5555
```

## Testing

```bash
# Create a bucket
curl -X PUT http://localhost:5555/my-bucket

# Upload a file
curl -X PUT -d "Hello World" http://localhost:5555/my-bucket/hello.txt

# Download a file
curl http://localhost:5555/my-bucket/hello.txt

# List buckets
curl http://localhost:5555/
```

## Project Structure

```
.
├── src/
│   └── api/
│       ├── app.py           # Flask application
│       ├── config.py        # Configuration management
│       ├── s3_api.py        # S3-compatible API implementation
│       ├── storage_backend.py # Storage backend interfaces
│       └── mock_fs_manager.py # Local storage implementation
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
└── Dockerfile             # Docker configuration
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
