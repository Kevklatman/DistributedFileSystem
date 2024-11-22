from setuptools import setup, find_packages

setup(
    name="distributed-file-system",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pytest>=7.0.0",
        "pytest-asyncio>=0.18.0",
        "aiohttp>=3.8.0",
        "pathlib>=1.0.1",
    ],
    python_requires=">=3.8",
)
