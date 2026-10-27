import os

import pytest

from .conftest import read_script, compile_script, find_handlers


class TestListTracksSyntax:
    def test_expected_handlers_exist(self):
        content = read_script("list_tracks.applescript")
        handlers = find_handlers(content)
        assert "mapTracks" in handlers
        assert "libraryTracks" in handlers
        assert "playlistTracks" in handlers

    @pytest.mark.skipif(not hasattr(os, "uname"), reason="requires macOS")
    def test_script_compiles(self):
        compile_script("list_tracks.applescript")


class TestListTracksStructure:
    def test_mapTracks_returns_record_list(self):
        content = read_script("list_tracks.applescript")
        assert "mappedTracks" in content
        assert "|music_id|" in content
        assert "|name|" in content
        assert "|artist|" in content
        assert "|album|" in content
        assert "|album_artist|" in content
        assert "|disc_number|" in content
        assert "|track_number|" in content
        assert "|filepath|" in content
        assert "|playcounts|" in content
        assert "|messages|" in content

    def test_mapTracks_handles_missing_files(self):
        content = read_script("list_tracks.applescript")
        assert "trackMessages" in content
        assert "on error" in content
        assert "missing value" in content
        assert "the file is missing" in content

    def test_libraryTracks_queries_all_tracks(self):
        content = read_script("list_tracks.applescript")
        assert "every track in it" in content

    def test_playlistTracks_takes_playlist_id(self):
        content = read_script("list_tracks.applescript")
        assert "playlistTracks" in content
        assert "playlist id playlistId" in content

    def test_mapTracks_uses_posix_path(self):
        content = read_script("list_tracks.applescript")
        assert "POSIX Path" in content

    def test_mapTracks_accesses_location(self):
        content = read_script("list_tracks.applescript")
        assert "aTrack's location" in content
