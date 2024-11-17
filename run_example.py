import os
import sys
import subprocess

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))

# Run the example with PYTHONPATH set
if __name__ == "__main__":
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    subprocess.run(
        ["python3", os.path.join(project_root, "examples/custom_policy_example.py")],
        env=env,
        cwd=project_root
    )
