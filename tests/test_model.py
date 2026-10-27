import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from songchro.model import (
    Track,
    Library,
    Playlist,
    NamedPlaylist,
    PlaylistFolder,
    SmartPlaylist,
    InvalidSyncError,
    NoSuchPlaylist,
    NoSuchTrack,
    CollectedErrors,
    SongchroException,
    HasJsonDataEncoder,
)
import json


class MockLibrary(Library):
    def __init__(self, tracks=None, playlists=None, music_root=None):
        super().__init__("Mock", "mock", music_root or Path("/music"), tracks or [], playlists or [])

    def find_track(self, track):
        return [t for t in self.tracks if t.key() == track.key()]

    def map_tracks(self, tracks, /, dry_run=False):
        for track in tracks:
            for t in self.tracks:
                if t.key() == track.key():
                    yield t
                    break


@pytest.fixture
def mock_library(tmp_path):
    return MockLibrary(music_root=Path(str(tmp_path)))


class TestTrack:
    def test_creation(self):
        t = Track(name="Song", artist="Artist", album="Album")
        assert t.name == "Song"
        assert t.artist == "Artist"
        assert t.album == "Album"

    def test_json_data(self):
        t = Track(
            name="Song",
            artist="Artist",
            album="Album",
            disc_number=1,
            track_number=3,
            filepath="/music/artist/song.mp3",
            playcounts={"plex": 5},
        )
        data = t.json_data()
        assert data["name"] == "Song"
        assert data["artist"] == "Artist"
        assert data["disc_number"] == 1

    def test_json_data_filters_none(self):
        t = Track(name="Song", artist=None)
        data = t.json_data()
        assert "artist" not in data

    def test_key(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", library=mock_library)
        assert t.key() == "/music/song.mp3"

    def test_equality(self, mock_library):
        t1 = Track(name="Song", filepath="/music/song.mp3", library=mock_library)
        t2 = Track(name="Different", filepath="/music/song.mp3", library=mock_library)
        t3 = Track(name="Song", filepath="/music/other.mp3", library=mock_library)
        assert t1 == t2
        assert t1 != t3

    def test_hash(self, mock_library):
        t1 = Track(name="Song", filepath="/music/song.mp3", library=mock_library)
        t2 = Track(name="Different", filepath="/music/song.mp3", library=mock_library)
        assert hash(t1) == hash(t2)

    def test_increment_plays(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={"mock": 0}, library=mock_library)
        t.increment_plays(1)
        assert t.playcounts["mock"] == 1


class TestHasJsonDataEncoder:
    def test_encodes_track(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={}, library=mock_library)
        result = json.loads(json.dumps(t, cls=HasJsonDataEncoder))
        assert result["name"] == "Song"

    def test_encodes_playlist(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={}, library=mock_library)
        p = Playlist("My Playlist", mock_library, tracks=[t])
        result = json.loads(json.dumps(p, cls=HasJsonDataEncoder))
        assert result["name"] == "My Playlist"


class TestPlaylist:
    def test_creation(self, mock_library):
        p = Playlist("Test", mock_library)
        assert p.name == "Test"
        assert p.library == mock_library
        assert list(p.tracks) == []

    def test_with_tracks(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={}, library=mock_library)
        p = Playlist("Test", mock_library, tracks=[t])
        assert list(p.tracks) == [t]

    def test_add_item_at_end(self, mock_library):
        p = Playlist("Test", mock_library)
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={}, library=mock_library)
        p.add_item(t, None)
        assert list(p.tracks) == [t]

    def test_add_item_after(self, mock_library):
        t1 = Track(name="Song 1", filepath="/music/song1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/song2.mp3", playcounts={}, library=mock_library)
        p = Playlist("Test", mock_library, tracks=[t1])
        p.add_item(t2, t1)
        assert list(p.tracks) == [t1, t2]

    def test_sync_tracks_insertrack(self, mock_library):
        t1 = Track(name="Song 1", filepath="/music/song1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/song2.mp3", playcounts={}, library=mock_library)
        mock_library._tracks = [t1, t2]
        p = Playlist("Test", mock_library, tracks=[t1])
        source = Playlist("Source", mock_library, tracks=[t2, t1])
        changed = p.sync_tracks(source)
        assert changed is True
        assert list(p.tracks) == [t1, t2]

    def test_sync_tracks_no_change(self, mock_library):
        t1 = Track(name="Song 1", filepath="/music/song1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/song2.mp3", playcounts={}, library=mock_library)
        mock_library._tracks = [t1, t2]
        p = Playlist("Test", mock_library, tracks=[t1, t2])
        source = Playlist("Source", mock_library, tracks=[t1, t2])
        changed = p.sync_tracks(source)
        assert changed is False

    def test_sync_tracks_dry_run(self, mock_library):
        t1 = Track(name="Song 1", filepath="/music/song1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/song2.mp3", playcounts={}, library=mock_library)
        mock_library._tracks = [t1, t2]
        p = Playlist("Test", mock_library, tracks=[t1])
        source = Playlist("Source", mock_library, tracks=[t2, t1])
        changed = p.sync_tracks(source, dry_run=True)
        assert changed is True
        assert list(p.tracks) == [t1]

    def test_str(self, mock_library):
        t = Track(name="Song", filepath="/music/song.mp3", playcounts={}, library=mock_library)
        p = Playlist("Test", mock_library, tracks=[t])
        assert "Test" in str(p)
        assert "1 tracks" in str(p)


class TestPlaylistFolder:
    def test_creation(self, mock_library):
        p = Playlist("Sub", mock_library)
        folder = PlaylistFolder("Folder", [p], mock_library)
        assert folder.name == "Folder"
        assert folder.sub_playlists == [p]

    def test_tracks_from_sub_playlists(self, mock_library):
        t1 = Track(name="Song 1", filepath="/music/s1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/s2.mp3", playcounts={}, library=mock_library)
        p1 = Playlist("Sub 1", mock_library, tracks=[t1])
        p2 = Playlist("Sub 2", mock_library, tracks=[t2])
        folder = PlaylistFolder("Folder", [p1, p2], mock_library)
        tracks = list(folder.tracks)
        assert len(tracks) == 2

    def test_tracks_deduplication(self, mock_library):
        t = Track(name="Song", filepath="/music/s.mp3", playcounts={}, library=mock_library)
        p1 = Playlist("Sub 1", mock_library, tracks=[t])
        p2 = Playlist("Sub 2", mock_library, tracks=[t])
        folder = PlaylistFolder("Folder", [p1, p2], mock_library)
        tracks = list(folder.tracks)
        assert len(tracks) == 1

    def test_sync_with_playlist_folder(self, mock_library, tmp_path):
        t1 = Track(name="Song 1", filepath="/music/s1.mp3", playcounts={}, library=mock_library)
        t2 = Track(name="Song 2", filepath="/music/s2.mp3", playcounts={}, library=mock_library)
        mock_library._tracks = [t1, t2]
        p1 = Playlist("Sub 1", mock_library, tracks=[t1])
        p2 = Playlist("Sub 2", mock_library, tracks=[t2])
        mock_library._playlists = [p1, p2]
        folder1 = PlaylistFolder("Folder", [p1], mock_library)
        folder2 = PlaylistFolder("Folder", [p1, p2], mock_library)
        changed = folder1.sync_tracks(folder2)
        assert changed is True
        assert len(folder1.sub_playlists) == 2

    def test_json_data(self, mock_library):
        p = Playlist("Sub", mock_library)
        folder = PlaylistFolder("Folder", [p], mock_library)
        data = folder.json_data()
        assert data["name"] == "Folder"
        assert data["sub_playlists"] == ["Sub"]


class TestSmartPlaylist:
    def test_creation(self, mock_library):
        sp = SmartPlaylist("Smart", {"key": "value"}, "key", mock_library)
        assert sp.name == "Smart"
        assert sp.smart_criteria == {"key": "value"}

    def test_tracks_without_criteria(self, mock_library):
        sp = SmartPlaylist("Smart", {}, "missing", mock_library)
        tracks = list(sp.tracks)
        assert tracks == []


class TestLibrary:
    def test_creation(self, tmp_path):
        lib = MockLibrary(music_root=tmp_path)
        assert lib.source == "Mock"
        assert lib.lib_type == "mock"

    def test_find_playlist(self, mock_library):
        p = Playlist("Test", mock_library)
        mock_library._playlists = [p]
        found = mock_library.find_playlist("Test")
        assert found == p

    def test_find_playlist_not_found(self, mock_library):
        with pytest.raises(NoSuchPlaylist):
            mock_library.find_playlist("Nonexistent")

    def test_standardize_path(self, mock_library, tmp_path):
        rel = mock_library.standardize_path(tmp_path / "sub" / "song.mp3")
        assert "sub" in rel and "song.mp3" in rel

    def test_json_data(self, mock_library):
        t = Track(name="Song", filepath="/music/s.mp3", playcounts={}, library=mock_library)
        p = Playlist("Test", mock_library, tracks=[t])
        mock_library._tracks = [t]
        mock_library._playlists = [p]
        data = mock_library.json_data()
        assert len(data["tracks"]) == 1
        assert len(data["playlists"]) == 1


class TestNamedPlaylist:
    def test_sync_tracks_raises(self, mock_library):
        np = NamedPlaylist("Test", mock_library)
        p = Playlist("Other", mock_library)
        with pytest.raises(InvalidSyncError):
            np.sync_tracks(p)

    def test_tracks_raises(self, mock_library):
        np = NamedPlaylist("Test", mock_library)
        with pytest.raises(NotImplementedError):
            list(np.tracks)

    def test_json_data(self, mock_library):
        np = NamedPlaylist("Test", mock_library)
        data = np.json_data()
        assert data["name"] == "Test"


class TestExceptions:
    def test_invalid_sync_error(self):
        err = InvalidSyncError(Playlist, SmartPlaylist)
        assert "Playlist" in str(err)
        assert "SmartPlaylist" in str(err)

    def test_collected_errors(self):
        inner = SongchroException("inner")
        err = CollectedErrors("multiple errors", [inner])
        assert err.errors == [inner]
