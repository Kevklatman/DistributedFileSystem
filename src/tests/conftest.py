"""Configuration for pytest."""

import os
import sys
from pathlib import Path
import pytest

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]
