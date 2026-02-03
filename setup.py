"""Setup script for gateway package."""

from setuptools import setup, find_packages

setup(
    name="lora-osm-notes-gateway",
    version="0.1.0",
    description="Gateway Meshtastic USB → OSM Notes for Raspberry Pi",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pyserial>=3.5",
        "protobuf>=4.25.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "lora-osmnotes=gateway.main:main",
        ],
    },
)
