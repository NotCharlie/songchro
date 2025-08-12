from setuptools import setup, find_packages
from songchro import __version__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="songchro",
    version=__version__,
    author="acourtneybrown",
    author_email="",  # Add author email if available
    description="Synchronize playlists between iTunes and Plex",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/acourtneybrown/songchro",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    entry_points={
        "console_scripts": [
            "songchro=songchro.cli:cli",
        ],
    },
)
