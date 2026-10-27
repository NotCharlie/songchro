import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from songchro.itunes import (
    ItunesTrack,
    ItunesPlaylist,
    ItunesSmartPlaylist,
    ItunesPlaylistFolder,
    ItunesLibrary,
    load_library,
    LIBRARY_TYPE,
)
from songchro.model import NoSuchTrack


@pytest.fixture
def mock_itunes_data():
    return {
        "Tracks": {
            "1": {
                "Track ID": 1,
                "Name": "Song One",
                "Artist": "Artist One",
                "Album": "Album One",
                "Album Artist": "Album Artist One",
                "Disc Number": 1,
                "Track Number": 1,
                "Play Count": 5,
                "Location": "file:///music/artist/song1.mp3",
            },
            "2": {
                "Track ID": 2,
                "Name": "Song Two",
                "Artist": "Artist Two",
                "Album": "Album Two",
                "Album Artist": "Album Artist Two",
                "Disc Number": 2,
                "Track Number": 3,
                "Play Count": 0,
                "Location": "file:///music/artist/song2.mp3",
            },
        },
        "Playlists": [
            {
                "Name": "Library",
                "Visible": True,
                "Distinguished Kind": "Library",
                "Playlist Persistent ID": "lib",
                "Playlist Items": [],
            },
            {
                "Name": "Favorites",
                "Visible": True,
                "Playlist Persistent ID": "fav",
                "Playlist Items": [
                    {"Track ID": 1},
                    {"Track ID": 2},
                ],
            },
        ],
    }


@pytest.fixture
def itunes_library(mock_itunes_data, tmp_path):
    return ItunesLibrary(
        music_root=tmp_path,
        itunes_library=mock_itunes_data,
        xml_path=str(tmp_path / "iTunes Music Library.xml"),
    )


class TestItunesTrack:
    def test_creation(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        assert t.name == "Song One"
        assert t.artist == "Artist One"
        assert t.album == "Album One"
        assert t.album_artist == "Album Artist One"
        assert t.disc_number == 1
        assert t.track_number == 1
        assert t.playcounts[LIBRARY_TYPE] == 5

    def test_key_is_track_id(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        assert t.key() == 1

    def test_equality_by_track_id(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t1 = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        t2 = ItunesTrack(track_data.copy(), str(itunes_library.music_root), itunes_library)
        assert t1 == t2

    def test_hash_by_track_id(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t1 = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        t2 = ItunesTrack(track_data.copy(), str(itunes_library.music_root), itunes_library)
        assert hash(t1) == hash(t2)

    def test_missing_location(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"].copy()
        del track_data["Location"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        assert t.filepath is None

    def test_increment_plays_logs(self, itunes_library, mock_itunes_data, capsys):
        track_data = mock_itunes_data["Tracks"]["1"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        t.increment_plays(5)


class TestItunesPlaylist:
    def test_creation(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        p = ItunesPlaylist("Test", [t], {}, itunes_library)
        assert p.name == "Test"
        assert len(list(p.tracks)) == 1


class TestItunesSmartPlaylist:
    def test_creation(self, itunes_library, mock_itunes_data):
        track_data = mock_itunes_data["Tracks"]["1"]
        t = ItunesTrack(track_data, str(itunes_library.music_root), itunes_library)
        sp = ItunesSmartPlaylist("Smart", {"criteria": True}, {}, [t], itunes_library)
        assert sp.name == "Smart"
        assert len(list(sp.tracks)) == 1


class TestItunesPlaylistFolder:
    def test_creation(self, itunes_library):
        folder = ItunesPlaylistFolder("Folder", [], {}, itunes_library)
        assert folder.name == "Folder"
        assert folder.sub_playlists == []


class TestItunesLibrary:
    def test_creation(self, itunes_library):
        assert itunes_library.source == "iTunes"
        assert itunes_library.lib_type == "itunes"

    def test_str(self, itunes_library):
        assert "ItunesLibrary" in str(itunes_library)

    def test_tracks(self, itunes_library):
        tracks = itunes_library.tracks
        assert len(tracks) == 2

    def test_playlists_excludes_library(self, itunes_library):
        playlists = itunes_library.playlists
        names = [p.name for p in playlists]
        assert "Library" not in names
        assert "Favorites" in names

    def test_playlist_tracks(self, itunes_library):
        playlists = itunes_library.playlists
        fav = [p for p in playlists if p.name == "Favorites"][0]
        tracks = list(fav.tracks)
        assert len(tracks) == 2

    def test_find_track_by_path(self, itunes_library):
        track = itunes_library.tracks[0]
        from songchro.model import Track as ModelTrack
        t = ModelTrack(name="Song", filepath=str(track.filepath), playcounts={})
        result = itunes_library.find_track(t)
        assert len(result) == 1

    def test_find_track_not_found(self, itunes_library):
        from songchro.model import Track as ModelTrack
        t = ModelTrack(name="Unknown", filepath="unknown.mp3", playcounts={})
        result = itunes_library.find_track(t)
        assert result == [None] or result == []

    def test_map_tracks(self, itunes_library):
        tracks = list(itunes_library.map_tracks(itunes_library.tracks))
        assert len([t for t in tracks if t is not None]) == 2

    def test_map_tracks_not_found_raises(self, itunes_library):
        from songchro.file_library import FileTrack
        t = FileTrack(name="Unknown", filepath=None, library=itunes_library)
        with pytest.raises(NoSuchTrack):
            list(itunes_library.map_tracks([t], dry_run=False))

    def test_map_tracks_dry_run_no_error(self, itunes_library):
        from songchro.file_library import FileTrack
        t = FileTrack(name="Unknown", filepath=None, library=itunes_library)
        result = list(itunes_library.map_tracks([t], dry_run=True))
        assert result == []

    def test_excludes_hidden_playlists(self, tmp_path, mock_itunes_data):
        mock_itunes_data["Playlists"].append({
            "Name": "Hidden",
            "Visible": False,
            "Playlist Persistent ID": "hidden",
            "Playlist Items": [],
        })
        lib = ItunesLibrary(
            music_root=tmp_path,
            itunes_library=mock_itunes_data,
            xml_path=str(tmp_path / "lib.xml"),
        )
        names = [p.name for p in lib.playlists]
        assert "Hidden" not in names

    def test_playlist_folder(self, tmp_path, mock_itunes_data):
        mock_itunes_data["Playlists"].append({
            "Name": "My Folder",
            "Visible": True,
            "Folder": True,
            "Playlist Persistent ID": "folder",
            "Playlist Items": [],
        })
        lib = ItunesLibrary(
            music_root=tmp_path,
            itunes_library=mock_itunes_data,
            xml_path=str(tmp_path / "lib.xml"),
        )
        folders = [p for p in lib.playlists if isinstance(p, ItunesPlaylistFolder)]
        assert len(folders) == 1

    def test_playlist_with_parent(self, tmp_path, mock_itunes_data):
        mock_itunes_data["Playlists"].append({
            "Name": "My Folder",
            "Visible": True,
            "Folder": True,
            "Playlist Persistent ID": "folder",
            "Playlist Items": [],
        })
        mock_itunes_data["Playlists"].append({
            "Name": "Sub Playlist",
            "Visible": True,
            "Playlist Persistent ID": "sub",
            "Parent Persistent ID": "folder",
            "Playlist Items": [{"Track ID": 1}],
        })
        lib = ItunesLibrary(
            music_root=tmp_path,
            itunes_library=mock_itunes_data,
            xml_path=str(tmp_path / "lib.xml"),
        )
        folder = lib.find_playlist("My Folder")
        assert len(folder.sub_playlists) == 1
        assert folder.sub_playlists[0].name == "Sub Playlist"


class TestLoadLibrary:
    def test_load_library(self, tmp_path, mock_itunes_data):
        xml_path = tmp_path / "iTunes Music Library.xml"
        import plistlib
        with open(xml_path, "wb") as f:
            plistlib.dump(mock_itunes_data, f)

        config = {"xml": str(xml_path), "music_root": str(tmp_path)}
        lib = load_library(config)
        assert lib.source == "iTunes"
        assert len(lib.tracks) == 2
