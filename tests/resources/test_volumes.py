import os

import pytest

from .conftest import read_script, compile_script, find_handlers


class TestVolumesSyntax:
    def test_expected_handlers_exist(self):
        content = read_script("volumes.applescript")
        handlers = find_handlers(content)
        assert "mountMusic" in handlers
        assert "unmountMusic" in handlers

    @pytest.mark.skipif(not hasattr(os, "uname"), reason="requires macOS")
    def test_script_compiles(self):
        compile_script("volumes.applescript")


class TestVolumesStructure:
    def test_mountMusic_takes_fpath(self):
        content = read_script("volumes.applescript")
        assert "mountMusic" in content
        assert "fpath" in content

    def test_mountMusic_uses_finder(self):
        content = read_script("volumes.applescript")
        assert "tell application \"Finder\"" in content
        assert "mount volume" in content

    def test_mountMusic_stores_result(self):
        content = read_script("volumes.applescript")
        assert "myMusic" in content
        assert "set myMusic to" in content

    def test_mountMusic_has_property(self):
        content = read_script("volumes.applescript")
        assert "property myMusic" in content

    def test_unmountMusic_ejects_via_finder(self):
        content = read_script("volumes.applescript")
        assert "eject disk" in content
        assert "eject disk myMusic" in content

    def test_unmountMusic_handles_not_mounted_error(self):
        content = read_script("volumes.applescript")
        assert "on error number -2753" in content
        assert "not mounted by `mountMusic`" in content

    def test_unmountMusic_returns_status(self):
        content = read_script("volumes.applescript")
        assert "return \"unmounted\"" in content
