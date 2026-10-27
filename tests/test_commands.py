import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from collections import defaultdict
from songchro.commands import (
    list_playlists,
    export_playlist,
    export_all_playlists,
    import_playlist,
    sync_plays,
)
from songchro.model import (
    Library,
    Track,
    Playlist,
    PlaylistFolder,
    SmartPlaylist,
    NamedPlaylist,
)
from songchro.file_library import FileLibrary


class MockLibrary(Library):
    def __init__(self, source="Mock", lib_type="mock", tracks=None, playlists=None):
        super().__init__(source, lib_type, Path("/music"), tracks or [], playlists or [])

    def find_track(self, track):
        return [t for t in self.tracks if t.key() == track.key()]

    def map_tracks(self, tracks, /, dry_run=False):
        for track in tracks:
            for t in self.tracks:
                if t.key() == track.key():
                    yield t
                    break

    def create_playlist(self, name, source, dry_run=False):
        tracks = list(source.tracks)
        new_playlist = Playlist(name, self, tracks=tracks)
        self._playlists.append(new_playlist)

    def save_tracks(self):
        pass


class MockFileLibrary(FileLibrary):
    def __init__(self, tracks=None, playlists=None):
        self.tracks_file = "/tmp/tracks.json"
        self.playlist_root = "/tmp/playlists"
        self.track_for_path = {}
        self._tracks = tracks or []
        self._playlists = playlists or []
        self.source = "File"
        self.lib_type = "file"
        self.music_root = Path("/music")

    def save_tracks(self):
        pass

    def create_playlist(self, name, source, dry_run=False):
        tracks = list(source.tracks)
        new_playlist = Playlist(name, self, tracks=tracks)
        self._playlists.append(new_playlist)


class TestListPlaylists:
    def test_list_simple(self, capsys):
        lib = MockLibrary()
        lib._playlists = [Playlist("B", lib), Playlist("A", lib)]
        list_playlists(lib, songs=False, simple=True, kind=Playlist)
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "B" in captured.out

    def test_list_with_songs(self, capsys):
        lib = MockLibrary()
        t = Track(name="Song", artist="Artist", album="Album", filepath="s.mp3", playcounts={}, library=lib)
        p = Playlist("Test", lib, tracks=[t])
        lib._playlists = [p]
        list_playlists(lib, songs=True, simple=False, kind=Playlist)
        captured = capsys.readouterr()
        assert "Song" in captured.out
        assert "Artist" in captured.out

    def test_list_filters_by_kind(self, capsys):
        lib = MockLibrary()
        p = Playlist("Plain", lib)
        sp = SmartPlaylist("Smart", {}, "key", lib)
        lib._playlists = [p, sp]
        list_playlists(lib, songs=False, simple=True, kind=Playlist)
        captured = capsys.readouterr()
        assert "Plain" in captured.out
        assert "Smart" not in captured.out

    def test_list_folders(self, capsys):
        lib = MockLibrary()
        p = Playlist("Sub", lib)
        folder = PlaylistFolder("Folder", [p], lib)
        lib._playlists = [folder]
        list_playlists(lib, songs=False, simple=True, kind=PlaylistFolder)
        captured = capsys.readouterr()
        assert "Folder" in captured.out


class TestExportPlaylist:
    def test_export_existing_playlist(self, capsys):
        source = MockLibrary(source="Source")
        t = Track(name="Song", filepath="s.mp3", playcounts={}, library=source)
        p = Playlist("Test", source, tracks=[t])
        source._playlists = [p]
        target = MockLibrary(source="Target")
        export_playlist(source, "Test", target, dry_run=False)
        captured = capsys.readouterr()
        assert "Found" in captured.out

    def test_export_nonexistent_playlist(self, capsys):
        source = MockLibrary(source="Source")
        target = MockLibrary(source="Target")
        from songchro.model import NoSuchPlaylist
        with pytest.raises(NoSuchPlaylist):
            export_playlist(source, "Nonexistent", target, dry_run=False)


class TestExportAllPlaylists:
    def test_export_all(self, capsys):
        source = MockLibrary(source="Source")
        p = Playlist("Test", source)
        sp = SmartPlaylist("Smart", {}, "key", source)
        source._playlists = [p, sp]
        target = MockLibrary(source="Target")
        export_all_playlists(source, target, dry_run=False)
        captured = capsys.readouterr()
        assert "Exporting all" in captured.out
        assert len([pl for pl in target.playlists if isinstance(pl, Playlist)]) == 1


class TestImportPlaylist:
    def test_import_playlist(self, capsys):
        source = MockLibrary(source="Source")
        t = Track(name="Song", filepath="s.mp3", playcounts={}, library=source)
        p = Playlist("Test", source, tracks=[t])
        source._playlists = [p]
        target = MockLibrary(source="Target")
        import_playlist(source, "Test", target, dry_run=False)
        captured = capsys.readouterr()
        assert "Created" in captured.out

    def test_import_nonexistent(self, capsys):
        source = MockLibrary(source="Source")
        target = MockLibrary(source="Target")
        from songchro.model import NoSuchPlaylist
        with pytest.raises(NoSuchPlaylist):
            import_playlist(source, "Nonexistent", target, dry_run=False)


class TestSyncPlays:
    def test_sync_no_changes(self, capsys):
        dest = MockFileLibrary()
        t = Track(name="Song", filepath="s.mp3", playcounts={"mock": 5}, library=dest)
        dest._tracks = [t]
        dest.track_for_path["s.mp3"] = t
        src = MockLibrary(source="mock_src")
        src_track = Track(name="Song", filepath="s.mp3", playcounts={"mock_src": 3}, library=src)
        src._tracks = [src_track]

        def mock_find_track(track):
            for t in src._tracks:
                if t.key() == track.key():
                    return [t]
            return []

        src.find_track = mock_find_track
        sync_plays(dest, {"mock_src": src}, dry_run=True)

    def test_sync_with_increase(self, capsys):
        dest = MockFileLibrary()
        t = Track(name="Song", filepath="s.mp3", playcounts={"mock": 3}, library=dest)
        dest._tracks = [t]
        dest.track_for_path["s.mp3"] = t
        src = MockLibrary(source="mock_src")
        src_track = Track(name="Song", filepath="s.mp3", playcounts={"mock_src": 10}, library=src)
        src._tracks = [src_track]

        def mock_find_track(track):
            for t in src._tracks:
                if t.key() == track.key():
                    return [t]
            return []

        src.find_track = mock_find_track
        sync_plays(dest, {"mock_src": src}, dry_run=True)

    def test_sync_updates_playcounts(self):
        dest = MockFileLibrary()
        t = Track(name="Song", filepath="s.mp3", playcounts={"mock": 3, "src1": 3, "src2": 3}, library=dest)
        dest._tracks = [t]
        dest.track_for_path["s.mp3"] = t
        src1 = MockLibrary(source="src1", lib_type="src1")
        src2 = MockLibrary(source="src2", lib_type="src2")
        src1_track = Track(name="Song", filepath="s.mp3", playcounts={"src1": 10}, library=src1)
        src2_track = Track(name="Song", filepath="s.mp3", playcounts={"src2": 5}, library=src2)
        src1._tracks = [src1_track]
        src2._tracks = [src2_track]

        def mock_find_track1(track):
            for t in src1._tracks:
                if t.key() == track.key():
                    return [t]
            return []

        def mock_find_track2(track):
            for t in src2._tracks:
                if t.key() == track.key():
                    return [t]
            return []

        src1.find_track = mock_find_track1
        src2.find_track = mock_find_track2
        sync_plays(dest, {"src1": src1, "src2": src2}, dry_run=False)
        # sync_plays propagates play counts across libraries and updates dest
        assert t.playcounts["src1"] == 12  # src1 gets incremented by src2's delta
        assert t.playcounts["src2"] == 12  # src2 gets incremented by src1's delta
