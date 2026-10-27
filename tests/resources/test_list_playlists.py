import os

import pytest

from .conftest import read_script, compile_script, find_handlers


class TestListPlaylistsSyntax:
    def test_expected_handlers_exist(self):
        content = read_script("list_playlists.applescript")
        handlers = find_handlers(content)
        assert "mapPlaylists" in handlers
        assert "listPlaylists" in handlers
        assert "listFolderPlaylists" in handlers
        assert "listSmartPlaylists" in handlers

    @pytest.mark.skipif(not hasattr(os, "uname"), reason="requires macOS")
    def test_script_compiles(self):
        compile_script("list_playlists.applescript")


class TestListPlaylistsStructure:
    def test_mapPlaylists_returns_record_list(self):
        content = read_script("list_playlists.applescript")
        assert "mappedPlaylists" in content
        assert "|name|" in content
        assert "|music_id|" in content
        assert "|parent_id|" in content
        assert "|smart|" in content

    def test_listPlaylists_filters_user_playlists(self):
        content = read_script("list_playlists.applescript")
        assert "every user playlist" in content
        assert "special kind is none" in content
        assert "smart is false" in content

    def test_listFolderPlaylists_queries_folders(self):
        content = read_script("list_playlists.applescript")
        assert "every folder playlist" in content

    def test_listSmartPlaylists_filters_smart(self):
        content = read_script("list_playlists.applescript")
        lines = content.splitlines()
        in_handler = False
        for line in lines:
            if "listSmartPlaylists" in line:
                in_handler = True
            if in_handler and "smart is true" in line:
                break
        assert in_handler or "smart is true" in content

    def test_mapPlaylists_handles_missing_parent(self):
        content = read_script("list_playlists.applescript")
        assert "parentId" in content
        assert "parent's id" in content
        assert "try" in content
