#!/usr/bin/env python3
"""Script to update import statements after directory restructuring."""
import os
import re


def update_imports(file_path):
    """Update import statements in a file."""
    with open(file_path, "r") as f:
        content = f.read()

    # Update storage core imports to infrastructure
    content = re.sub(
        r"from (?:src\.)?storage\.core\.", "from storage.infrastructure.", content
    )
    content = re.sub(
        r"import (?:src\.)?storage\.core\.", "import storage.infrastructure.", content
    )

    # Update api core imports to services
    content = re.sub(r"from (?:src\.)?api\.core\.", "from api.services.", content)
    content = re.sub(r"import (?:src\.)?api\.core\.", "import api.services.", content)

    # Special case for relative imports
    content = re.sub(r"from \.\.(core)\.", r"from ..services.", content)

    with open(file_path, "w") as f:
        f.write(content)


def main():
    """Main function to update imports in all Python files."""
    root_dir = "/Users/kevinklatman/Development/Code/DistributedFileSystem"

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    update_imports(file_path)
                    print(f"Updated imports in {file_path}")
                except Exception as e:
                    print(f"Error updating {file_path}: {str(e)}")


if __name__ == "__main__":
    main()
