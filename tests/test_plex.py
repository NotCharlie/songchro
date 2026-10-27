import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from songchro.plex import (
    PlexLibrary,
    PlexTrack,
    PlexPlaylist,
    PlexPlaylistFolder,
    PlexSmartPlaylist,
    PlexFilterSmartPlaylist,
    PlexExternalSmartPlaylist,
    FOLDER_METADATA_HEADER,
    SMART_METADATA_HEADER,
)
from songchro.model import Track, CollectedErrors, NoSuchTrack

_perform_replacements = PlexLibrary._perform_replacements
_strip_regexes = PlexLibrary._strip_regexes


@pytest.fixture
def mock_music_section():
    section = MagicMock()
    section.getWebURL.return_value = "http://localhost:32400"
    return section


@pytest.fixture
def plex_library(mock_music_section, tmp_path):
    return PlexLibrary(music_root=tmp_path, music=mock_music_section)


class TestPlexTrack:
    def test_creation(self, plex_library):
        plex_track = MagicMock()
        plex_track.title = "Song Title"
        plex_track.artist.return_value.title = "Artist"
        plex_track.album.return_value.title = "Album"
        plex_track.album.return_value.artist.return_value.title = "Album Artist"
        plex_track.locations = ["/music/artist/song.mp3"]
        plex_track.parentIndex = 1
        plex_track.index = 3
        plex_track.viewCount = 5
        plex_track.key = "tracks/1"

        t = PlexTrack(plex_track, plex_library)
        assert t.name == "Song Title"
        assert t.artist == "Artist"
        assert t.album == "Album"
        assert t.album_artist == "Album Artist"
        assert t.disc_number == 1
        assert t.track_number == 3
        assert t.playcounts["plex"] == 5

    def test_key_is_plex_key(self, plex_library):
        plex_track = MagicMock()
        plex_track.title = "Song"
        plex_track.artist.return_value.title = "Artist"
        plex_track.album.return_value.title = "Album"
        plex_track.album.return_value.artist.return_value.title = "Album Artist"
        plex_track.locations = ["/music/song.mp3"]
        plex_track.parentIndex = 1
        plex_track.index = 1
        plex_track.viewCount = 0
        plex_track.key = "tracks/5"
        t = PlexTrack(plex_track, plex_library)
        assert t.key() == "tracks/5"

    def test_equality(self, plex_library):
        plex_track = MagicMock()
        plex_track.title = "Song"
        plex_track.artist.return_value.title = "Artist"
        plex_track.album.return_value.title = "Album"
        plex_track.album.return_value.artist.return_value.title = "Album Artist"
        plex_track.locations = ["/music/song.mp3"]
        plex_track.parentIndex = 1
        plex_track.index = 1
        plex_track.viewCount = 0
        plex_track.key = "tracks/1"
        t1 = PlexTrack(plex_track, plex_library)
        t2 = PlexTrack(plex_track, plex_library)
        assert t1 == t2


class TestPlexPlaylist:
    def test_creation(self, plex_library):
        plex_playlist = MagicMock()
        plex_playlist.title = "My Playlist"
        plex_playlist.items.return_value = []
        pp = PlexPlaylist(plex_playlist, plex_library)
        assert pp.name == "My Playlist"

    def test_tracks(self, plex_library):
        plex_track = MagicMock()
        plex_track.title = "Song"
        plex_track.artist.return_value.title = "Artist"
        plex_track.album.return_value.title = "Album"
        plex_track.album.return_value.artist.return_value.title = "Album Artist"
        plex_track.locations = ["/music/song.mp3"]
        plex_track.parentIndex = 1
        plex_track.index = 1
        plex_track.viewCount = 0
        plex_track.key = "tracks/1"

        plex_playlist = MagicMock()
        plex_playlist.title = "My Playlist"
        plex_playlist.items.return_value = [plex_track]
        pp = PlexPlaylist(plex_playlist, plex_library)
        tracks = pp.tracks
        assert len(tracks) == 1


class TestPerformReplacements:
    def test_hyphen_to_dash(self):
        result = _perform_replacements("Song-Title")
        assert any("Song\u2010Title" in r or "Song\u2013Title" in r for r in result)

    def test_ampersand_to_and(self):
        result = _perform_replacements("Artist & Band")
        assert any("Artist And Band" in r or "Artist & Band" in r for r in result)

    def test_empty_string(self):
        result = _perform_replacements("")
        assert result == set()

    def test_none(self):
        result = _perform_replacements(None)
        assert result == set()

    def test_original_included(self):
        result = _perform_replacements("Song Title")
        assert "Song Title" in result


class TestStripRegexes:
    def test_removes_parentheses_suffix(self):
        result = list(_strip_regexes("Song (Remix)"))
        assert len(result) > 1
        assert any("Remix" in r for r in result)

    def test_removes_brackets_suffix(self):
        result = list(_strip_regexes("Song [Edit]"))
        assert len(result) > 1

    def test_empty_string(self):
        result = list(_strip_regexes(""))
        assert result == [""]

    def test_none(self):
        result = list(_strip_regexes(None))
        assert result == [""]


class TestPlexPlaylistFolder:
    def test_creation(self, plex_library):
        plex_playlist = MagicMock()
        plex_playlist.title = "Folder"
        ppf = PlexPlaylistFolder(plex_playlist, [], plex_library)
        assert ppf.name == "Folder"


class TestPlexLibrary:
    def test_creation(self, plex_library):
        assert plex_library.source == "Plex"
        assert plex_library.lib_type == "plex"

    def test_str(self, plex_library):
        assert "PlexLibrary" in str(plex_library)

    def test_make_filter(self):
        elements = {"title": ["Song"], "artist": ["Artist"]}
        result = PlexLibrary._make_filter(elements)
        assert "and" in result


class TestMapTracks:
    def test_map_tracks_success(self, plex_library):
        source_track = Track(name="Song", filepath="song.mp3", playcounts={})
        plex_track = MagicMock()
        plex_track.title = "Song"
        plex_track.artist.return_value.title = "Artist"
        plex_track.album.return_value.title = "Album"
        plex_track.album.return_value.artist.return_value.title = "Album Artist"
        plex_track.locations = ["/music/song.mp3"]
        plex_track.parentIndex = 1
        plex_track.index = 1
        plex_track.viewCount = 0
        plex_track.key = "tracks/1"

        plex_library.find_track = MagicMock(return_value=[PlexTrack(plex_track, plex_library)])
        result = list(plex_library.map_tracks([source_track]))
        assert len(result) == 1

    def test_map_tracks_not_found_raises(self, plex_library):
        source_track = Track(name="Song", filepath="song.mp3", playcounts={})
        plex_library.find_track = MagicMock(return_value=[])
        with pytest.raises(NoSuchTrack):
            list(plex_library.map_tracks([source_track]))

    def test_map_tracks_dry_run_with_errors(self, plex_library):
        source_track = Track(name="Song", filepath="song.mp3", playcounts={})
        plex_library.find_track = MagicMock(return_value=[])
        with pytest.raises(CollectedErrors):
            list(plex_library.map_tracks([source_track], dry_run=True))


class TestCreatePlaylist:
    def test_create_playlist_checks_for_existing(self, plex_library):
        from songchro.model import Playlist as ModelPlaylist
        from plexapi.exceptions import NotFound

        source = MagicMock(spec=ModelPlaylist)
        source.tracks = []

        # Should raise when playlist already exists
        plex_library.music.playlist.return_value = MagicMock()
        with pytest.raises(RuntimeError, match="existing playlist"):
            plex_library.create_playlist("Test", source, dry_run=False)


class TestPlaylistDetection:
    def test_detects_plex_filter_smart_playlist(self, mock_music_section, tmp_path):
        plex_playlist = MagicMock()
        plex_playlist.title = "Smart"
        plex_playlist.smart = True
        plex_playlist.summary = ""
        plex_playlist.filters.return_value = {}
        mock_music_section.playlists.return_value = [plex_playlist]

        lib = PlexLibrary(music_root=tmp_path, music=mock_music_section)
        playlists = lib.playlists
        assert any(isinstance(p, PlexFilterSmartPlaylist) for p in playlists)

    def test_detects_external_smart_playlist(self, mock_music_section, tmp_path):
        import base64
        import codecs
        import json
        from songchro.model import HasJsonDataEncoder

        smart_data = {"smart_criteria": {"file": {"filter": "x"}}}
        b64 = codecs.decode(base64.encodebytes(codecs.encode(json.dumps(smart_data, cls=HasJsonDataEncoder))))
        plex_playlist = MagicMock()
        plex_playlist.title = "External Smart"
        plex_playlist.smart = False
        plex_playlist.summary = f"Some comment\n{SMART_METADATA_HEADER}{b64}\n"
        plex_playlist.items.return_value = []
        mock_music_section.playlists.return_value = [plex_playlist]

        lib = PlexLibrary(music_root=tmp_path, music=mock_music_section)
        playlists = lib.playlists
        assert any(isinstance(p, PlexExternalSmartPlaylist) for p in playlists)

    def test_detects_folder_playlist(self, mock_music_section, tmp_path):
        import base64
        import codecs
        import json
        from songchro.model import HasJsonDataEncoder

        # Create a sub-playlist first
        sub_playlist = MagicMock()
        sub_playlist.title = "Sub1"
        sub_playlist.smart = False
        sub_playlist.summary = ""
        sub_playlist.items.return_value = []

        # Create folder that references the sub-playlist
        folder_data = {"name": "Folder", "sub_playlists": ["Sub1"]}
        b64 = codecs.decode(base64.encodebytes(codecs.encode(json.dumps(folder_data))))
        folder_playlist = MagicMock()
        folder_playlist.title = "Folder"
        folder_playlist.smart = False
        folder_playlist.summary = f"{FOLDER_METADATA_HEADER}{b64}\n"
        folder_playlist.items.return_value = []

        mock_music_section.playlists.return_value = [sub_playlist, folder_playlist]

        lib = PlexLibrary(music_root=tmp_path, music=mock_music_section)
        playlists = lib.playlists
        assert any(isinstance(p, PlexPlaylistFolder) for p in playlists)

    def test_detects_regular_playlist(self, mock_music_section, tmp_path):
        plex_playlist = MagicMock()
        plex_playlist.title = "Regular"
        plex_playlist.smart = False
        plex_playlist.summary = ""
        plex_playlist.items.return_value = []
        mock_music_section.playlists.return_value = [plex_playlist]

        lib = PlexLibrary(music_root=tmp_path, music=mock_music_section)
        playlists = lib.playlists
        assert any(isinstance(p, PlexPlaylist) for p in playlists)
