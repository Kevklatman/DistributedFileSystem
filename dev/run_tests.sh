#!/bin/bash

# Build the development image
docker build -t dfs-dev -f Dockerfile.dev ..

# Run tests in a clean container
docker run --rm -it \
    -v "$(pwd)/..:/app" \
    -v "dfs-test-cache:/data" \
    --network host \
    dfs-dev \
    pytest tests/unit tests/integration -v --cov=src

# Optional: Run type checking
# docker run --rm -it dfs-dev mypy src/

# Optional: Run linting
# docker run --rm -it dfs-dev black src/ --check
# docker run --rm -it dfs-dev flake8 src/
