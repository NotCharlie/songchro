import os
import sys
import subprocess

import pytest

RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "resources")


@pytest.fixture(autouse=True)
def skip_on_non_macos(request):
    if sys.platform != "darwin":
        pytest.skip("requires macOS")


def get_script_path(script_name):
    return os.path.join(RESOURCES_DIR, script_name)


def read_script(script_name):
    with open(get_script_path(script_name), "r") as f:
        return f.read()


def compile_script(script_name):
    """Compile an AppleScript to check for syntax errors. Raises on failure."""
    result = subprocess.run(
        ["osacompile", "-o", "/dev/null", get_script_path(script_name)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stderr)
    return result


def find_handlers(script_content):
    """Extract handler names from AppleScript content."""
    handlers = []
    for line in script_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("on ") and "(" in stripped:
            handler_name = stripped[3:stripped.index("(")]
            handlers.append(handler_name)
        elif stripped.startswith("to ") and "(" in stripped:
            handler_name = stripped[3:stripped.index("(")]
            handlers.append(handler_name)
    return handlers
