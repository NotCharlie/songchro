#!/usr/bin/env python3
"""
Simple test script to verify the CLI skeleton works properly.
"""

import subprocess
import sys


def run_command(command):
    """Run a command and print the output."""
    print(f"\n=== Running: {command} ===")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(e.stderr)
        return False


def main():
    """Run a series of tests to verify the CLI skeleton."""
    # Install the package in development mode
    print("Installing package in development mode...")
    if not run_command("pip install -e ."):
        print("Failed to install package. Exiting.")
        return 1

    # Test commands
    commands = [
        "songchro --help",
        "songchro --version",
        "songchro itunes --help",
        "songchro itunes list",
        "songchro itunes export 'Test Playlist'",
        "songchro plex --help",
        "songchro plex list",
        "songchro plex import 'Test Playlist'",
        "songchro sync 'Source Playlist' 'Destination Playlist'",
    ]

    success = True
    for cmd in commands:
        if not run_command(cmd):
            success = False

    if success:
        print("\nAll tests passed successfully!")
        return 0
    else:
        print("\nSome tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
