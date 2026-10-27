import os

import pytest

from .conftest import get_script_path, read_script, find_handlers


class TestResourcesExist:
    """Verify all expected AppleScript resources are present."""

    EXPECTED_SCRIPTS = [
        "list_playlists.applescript",
        "list_tracks.applescript",
        "volumes.applescript",
    ]

    @pytest.mark.parametrize("script_name", EXPECTED_SCRIPTS)
    def test_script_file_exists(self, script_name):
        path = get_script_path(script_name)
        assert os.path.isfile(path), f"{script_name} not found"

    @pytest.mark.parametrize("script_name", EXPECTED_SCRIPTS)
    def test_script_not_empty(self, script_name):
        content = read_script(script_name)
        assert len(content.strip()) > 0, f"{script_name} is empty"

    @pytest.mark.parametrize("script_name", EXPECTED_SCRIPTS)
    def test_script_has_handlers(self, script_name):
        content = read_script(script_name)
        handlers = find_handlers(content)
        assert len(handlers) > 0, f"{script_name} has no handlers"


class TestAllScriptHandlers:
    """Verify all scripts have their expected handlers."""

    EXPECTED_HANDLERS = {
        "list_playlists.applescript": [
            "mapPlaylists",
            "listPlaylists",
            "listFolderPlaylists",
            "listSmartPlaylists",
        ],
        "list_tracks.applescript": ["mapTracks", "libraryTracks", "playlistTracks"],
        "volumes.applescript": ["mountMusic", "unmountMusic"],
    }

    @pytest.mark.parametrize("script_name,expected", EXPECTED_HANDLERS.items())
    def test_all_handlers_present(self, script_name, expected):
        content = read_script(script_name)
        handlers = find_handlers(content)
        for handler in expected:
            assert handler in handlers, f"{script_name} missing handler: {handler}"


class TestAppleScriptStructure:
    """Verify scripts use expected AppleScript constructs."""

    def test_scripts_use_music_app(self):
        for script in ["list_playlists.applescript", "list_tracks.applescript"]:
            content = read_script(script)
            assert 'application "Music"' in content, f"{script} should target Music app"

    def test_volumes_uses_finder(self):
        content = read_script("volumes.applescript")
        assert 'application "Finder"' in content

    def test_playlists_script_uses_terms_from(self):
        content = read_script("list_playlists.applescript")
        assert 'using terms from application "Music"' in content

    def test_tracks_script_uses_terms_from(self):
        content = read_script("list_tracks.applescript")
        assert 'using terms from application "Music"' in content
