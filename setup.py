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
    python_requires=">=3.6",
    install_requires=[
        "plexapi>=4.17.0",
        "requests>=2.32.4",
        "spotipy>=2.25.1",
        "click>=8.1.7",
    ],
    entry_points={
        "console_scripts": [
            "songchro=songchro.cli:cli",
        ],
    },
)
