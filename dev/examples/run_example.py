import os
import subprocess

# Get the project root directory
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Run the example with PYTHONPATH set
if __name__ == "__main__":
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    subprocess.run(
        [
            "python3",
            os.path.join(project_root, "src/examples/custom_policy_example.py"),
        ],
        env=env,
        cwd=project_root,
    )
