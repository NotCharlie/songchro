import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from songchro.file_library import (
    FileTrack,
    FilePlaylist,
    FilePlaylistFolder,
    FileSmartPlaylist,
    FileExternalSmartPlaylist,
    FileLibrary,
    mp3_m4a_files,
    load_library,
    InvalidTrack,
    LIBRARY_TYPE,
)
from songchro.model import Track, Playlist, PlaylistFolder, SmartPlaylist, NoSuchPlaylist


@pytest.fixture
def music_root(tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    return str(music)


@pytest.fixture
def playlist_root(tmp_path):
    pl = tmp_path / "playlists"
    pl.mkdir()
    return str(pl)


@pytest.fixture
def tracks_file(tmp_path):
    return str(tmp_path / "tracks.json")


@pytest.fixture
def file_library(tracks_file, playlist_root, music_root):
    return FileLibrary(tracks_file, playlist_root, music_root)


class TestMp3M4aFiles:
    def test_finds_mp3_files(self, tmp_path):
        (tmp_path / "song.mp3").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 1
        assert files[0].name == "song.mp3"

    def test_finds_m4a_files(self, tmp_path):
        (tmp_path / "song.m4a").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 1

    def test_ignores_other_extensions(self, tmp_path):
        (tmp_path / "song.flac").touch()
        (tmp_path / "song.mp3").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 1

    def test_recursive(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "song.mp3").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 1

    def test_skips_hidden_directories(self, tmp_path):
        (tmp_path / "#hidden").mkdir()
        (tmp_path / "#hidden" / "song.mp3").touch()
        (tmp_path / "visible").mkdir()
        (tmp_path / "visible" / "song2.mp3").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 1
        assert files[0].name == "song2.mp3"

    def test_skips_eadirs(self, tmp_path):
        (tmp_path / "@eaDir").mkdir()
        (tmp_path / "@eaDir" / "song.mp3").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 0

    def test_not_directory_raises(self, tmp_path):
        file = tmp_path / "file.txt"
        file.touch()
        with pytest.raises(ValueError):
            list(mp3_m4a_files(file))

    def test_case_insensitive(self, tmp_path):
        (tmp_path / "song.MP3").touch()
        (tmp_path / "song.M4A").touch()
        files = list(mp3_m4a_files(tmp_path))
        assert len(files) == 2


class TestFileTrack:
    def test_creation(self, file_library):
        t = FileTrack(name="Song", artist="Artist", filepath="song.mp3", library=file_library)
        assert t.name == "Song"
        assert t.artist == "Artist"

    def test_from_dict(self, file_library):
        dct = {"name": "Song", "artist": "Artist", "filepath": "song.mp3"}
        t = FileTrack.from_dict(dct, file_library)
        assert t.name == "Song"

    def test_json_data(self, file_library):
        t = FileTrack(name="Song", filepath="song.mp3", metadata={"title": "Song"}, library=file_library)
        data = t.json_data()
        assert data["name"] == "Song"
        assert "metadata" in data


class TestFilePlaylist:
    def test_creation(self, file_library, playlist_root):
        p = FilePlaylist("Test", Path(playlist_root) / "resources.json", file_library, tracks=[])
        assert p.name == "Test"

    def test_json_data(self, file_library, playlist_root):
        t = FileTrack(name="Song", filepath="song.mp3", library=file_library)
        p = FilePlaylist("Test", Path(playlist_root) / "resources.json", file_library, tracks=[t])
        data = p.json_data()
        assert data["name"] == "Test"
        assert data["tracks"] == ["song.mp3"]

    def test_write_file(self, file_library, playlist_root):
        p = FilePlaylist("Test", Path(playlist_root) / "resources.json", file_library, tracks=[])
        p.write_file()
        assert (Path(playlist_root) / "resources.json").exists()
        with open(Path(playlist_root) / "resources.json") as f:
            data = json.load(f)
        assert data["name"] == "Test"


class TestFilePlaylistFolder:
    def test_creation(self, file_library, playlist_root):
        p = FilePlaylist("Sub", Path(playlist_root) / "sub.json", file_library, tracks=[])
        folder = FilePlaylistFolder("Folder", [p], Path(playlist_root) / "folder.json", file_library)
        assert folder.name == "Folder"

    def test_write_file(self, file_library, playlist_root):
        p = FilePlaylist("Sub", Path(playlist_root) / "sub.json", file_library, tracks=[])
        folder = FilePlaylistFolder("Folder", [p], Path(playlist_root) / "folder.json", file_library)
        folder.write_file()
        assert (Path(playlist_root) / "folder.json").exists()


class TestFileSmartPlaylist:
    def test_creation(self, file_library, playlist_root):
        criteria = {"file": {"filter": "title == 'Test'"}}
        sp = FileSmartPlaylist("Smart", criteria, Path(playlist_root) / "smart.json", file_library)
        assert sp.name == "Smart"

    def test_filter_function_returned(self, file_library, playlist_root):
        criteria = {"file": {"filter": "title == 'Test'"}}
        sp = FileSmartPlaylist("Smart", criteria, Path(playlist_root) / "smart.json", file_library)
        fn = sp._filter()
        assert callable(fn)


class TestFileExternalSmartPlaylist:
    def test_tracks_empty(self, file_library, playlist_root):
        criteria = {"plex": {"filter": "title == 'Test'"}}
        sp = FileExternalSmartPlaylist("Smart", criteria, Path(playlist_root) / "smart.json", file_library)
        assert list(sp.tracks) == []


class TestFileLibrary:
    def test_creation(self, tracks_file, playlist_root, music_root):
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        assert lib.source == "File"
        assert lib.lib_type == "file"

    def test_load_playlists(self, tracks_file, playlist_root, music_root):
        pl_file = Path(playlist_root) / "resources.json"
        pl_file.write_text(json.dumps({"name": "Test", "tracks": []}))
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        assert len(lib.playlists) == 1
        assert lib.playlists[0].name == "Test"

    def test_load_playlist_folder(self, tracks_file, playlist_root, music_root):
        Path(playlist_root) / "sub.json"
        (Path(playlist_root) / "sub.json").write_text(json.dumps({"name": "Sub", "tracks": []}))
        (Path(playlist_root) / "folder.json").write_text(json.dumps({"name": "Folder", "sub_playlists": ["Sub"]}))
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        folder = lib.find_playlist("Folder")
        assert len(folder.sub_playlists) == 1

    def test_load_smart_playlist(self, tracks_file, playlist_root, music_root):
        (Path(playlist_root) / "smart.json").write_text(json.dumps({"name": "Smart", "smart_criteria": {"file": {"filter": "x"}}}))
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        from songchro.file_library import FileSmartPlaylist
        sp = lib.find_playlist("Smart")
        assert isinstance(sp, FileSmartPlaylist)

    def test_load_external_smart_playlist(self, tracks_file, playlist_root, music_root):
        (Path(playlist_root) / "smart.json").write_text(json.dumps({"name": "Smart", "smart_criteria": {"plex": {"filter": "x"}}}))
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        from songchro.file_library import FileExternalSmartPlaylist
        sp = lib.find_playlist("Smart")
        assert isinstance(sp, FileExternalSmartPlaylist)

    def test_find_playlist_not_found(self, file_library):
        with pytest.raises(NoSuchPlaylist):
            file_library.find_playlist("Nonexistent")

    def test_str(self, file_library):
        assert "FileLibrary" in str(file_library)

    def test_map_tracks(self, file_library, music_root):
        t = FileTrack(name="Song", filepath="song.mp3", library=file_library)
        file_library.track_for_path["song.mp3"] = t
        result = list(file_library.map_tracks([t]))
        assert len(result) == 1

    def test_map_tracks_not_found(self, file_library):
        from songchro.model import NoSuchTrack
        t = FileTrack(name="Song", filepath=None, library=file_library)
        with pytest.raises(NoSuchTrack):
            list(file_library.map_tracks([t], dry_run=False))

    def test_map_tracks_dry_run_no_error(self, file_library):
        from songchro.model import NoSuchTrack
        t = FileTrack(name="Song", filepath=None, library=file_library)
        result = list(file_library.map_tracks([t], dry_run=True))
        assert result == []

    def test_find_track(self, file_library):
        t = FileTrack(name="Song", filepath="song.mp3", library=file_library)
        file_library.track_for_path["song.mp3"] = t
        result = file_library.find_track(t)
        assert result == [t]

    def test_save_and_load_tracks(self, tracks_file, playlist_root, music_root):
        lib = FileLibrary(tracks_file, playlist_root, music_root)
        t = FileTrack(name="Song", filepath="song.mp3", library=lib)
        lib.track_for_path["song.mp3"] = t
        lib.save_tracks()
        lib2 = FileLibrary(tracks_file, playlist_root, music_root)
        assert "song.mp3" in lib2.track_for_path


class TestLoadLibrary:
    def test_load_library(self, tracks_file, playlist_root, music_root):
        config = {"tracks": tracks_file, "root": playlist_root, "music_root": music_root}
        lib = load_library(config)
        assert lib.source == "File"


class TestUpdateMetadata:
    def test_rejects_path_outside_music_root(self, file_library, music_root, tmp_path):
        outside = tmp_path / "other"
        outside.mkdir()
        with pytest.raises(SystemExit):
            file_library.update_metadata(str(outside))

    def test_rejects_path_outside_music_root_absolute(self, file_library, music_root, tmp_path):
        outside = tmp_path.resolve() / "other"
        outside.mkdir()
        with pytest.raises(SystemExit):
            file_library.update_metadata(str(outside))

    def test_accepts_subdir_inside_music_root(self, file_library, music_root, tmp_path):
        subdir = Path(music_root) / "artist"
        subdir.mkdir()
        (subdir / "song.mp3").touch()
        with patch.object(file_library, "save_tracks"):
            with patch("songchro.file_library.mp3_m4a_files") as mock_files:
                mock_files.return_value = [subdir / "song.mp3"]
                with patch("songchro.file_library.FileTrack.from_file") as mock_from_file:
                    mock_from_file.return_value = MagicMock()
                    file_library.update_metadata(str(subdir))
        mock_files.assert_called_once_with(subdir)

    def test_accepts_music_root_itself(self, file_library, music_root, tmp_path):
        with patch.object(file_library, "save_tracks"):
            with patch("songchro.file_library.mp3_m4a_files") as mock_files:
                mock_files.return_value = []
                file_library.update_metadata(music_root)
        music_root_path = Path(music_root).resolve()
        mock_files.assert_called_once_with(music_root_path)

    def test_updates_tracks_in_dict(self, file_library, music_root, tmp_path):
        subdir = Path(music_root) / "album"
        subdir.mkdir()
        (subdir / "track.mp3").touch()
        mock_track = MagicMock()
        with patch("songchro.file_library.mp3_m4a_files") as mock_files:
            mock_files.return_value = [subdir / "track.mp3"]
            with patch("songchro.file_library.FileTrack.from_file", return_value=mock_track):
                with patch.object(file_library, "save_tracks"):
                    file_library.update_metadata(str(subdir))
        relpath = file_library.standardize_path(subdir / "track.mp3")
        assert relpath in file_library.track_for_path
        assert file_library.track_for_path[relpath] is mock_track

    def test_preserves_playcounts_on_update(self, file_library, music_root, tmp_path):
        subdir = Path(music_root) / "album"
        subdir.mkdir()
        (subdir / "track.mp3").touch()
        existing_track = MagicMock()
        existing_track.playcounts = {"2024-01-01": 3}
        relpath = file_library.standardize_path(subdir / "track.mp3")
        file_library.track_for_path[relpath] = existing_track
        new_track = MagicMock()
        new_track.playcounts = {}
        with patch("songchro.file_library.mp3_m4a_files") as mock_files:
            mock_files.return_value = [subdir / "track.mp3"]
            with patch("songchro.file_library.FileTrack.from_file", return_value=new_track):
                with patch.object(file_library, "save_tracks"):
                    file_library.update_metadata(str(subdir))
        assert file_library.track_for_path[relpath] is new_track
        assert file_library.track_for_path[relpath].playcounts == {"2024-01-01": 3}

    def test_skips_metadata_errors(self, file_library, music_root, tmp_path):
        subdir = Path(music_root) / "album"
        subdir.mkdir()
        (subdir / "bad.mp3").touch()
        (subdir / "good.mp3").touch()
        from songchro.music_metadata import MetadataError
        mock_bad = MagicMock()
        mock_good = MagicMock()
        mock_good.playcounts = {}
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                raise MetadataError("bad file")
            call_count += 1
            return mock_good

        with patch("songchro.file_library.mp3_m4a_files") as mock_files:
            mock_files.return_value = [subdir / "bad.mp3", subdir / "good.mp3"]
            with patch("songchro.file_library.FileTrack.from_file", side_effect=side_effect):
                with patch.object(file_library, "save_tracks"):
                    file_library.update_metadata(str(subdir))
        good_relpath = file_library.standardize_path(subdir / "good.mp3")
        assert good_relpath in file_library.track_for_path
