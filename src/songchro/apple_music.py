import atexit
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
import importlib.resources
from typing import Any

try:
    import applescript
except ImportError:
    # macOS-only module; provide stubs for non-macOS environments
    class _FakeApplescript:  # noqa: N801
        class ScriptError(Exception):
            pass
        def AppleScript(self, **_):  # noqa: N802
            raise RuntimeError("applescript requires macOS")

    applescript = _FakeApplescript()

import structlog

from songchro.model import Library, NamedPlaylist, Playlist, SmartPlaylist, PlaylistFolder, Track

LIBRARY_TYPE = "apple_music"

log = structlog.get_logger()


class AppleMusicTrack(Track):
    def __init__(self, music_track: dict[str, Any], library: "AppleMusicLibrary"):
        props = music_track.copy()
        props["filepath"] = library.standardize_path(props["filepath"])
        self.music_id = props["music_id"]
        del props["music_id"]
        messages = props.get("messages")
        del props["messages"]
        if messages:
            log.warning("messages from AppleScript", messages=messages, music_id=self.music_id)
        super().__init__(library=library, **props)


class AppleMusicPlaylist(Playlist):
    def __init__(self, name: str, music_id: int, parent_id: int, library: "AppleMusicLibrary", **_):
        super().__init__(name, library, [])
        self.music_id = music_id
        self.music_parent_id = parent_id

    @property
    def tracks(self) -> Iterable[Track]:
        try:
            music_tracks = self.library._track_scpt.call("playlistTracks", self.music_id)
        except applescript.ScriptError as e:
            log.warning("failed on `playlistTracks` script", e=e, name=self.name)
        else:
            for music_track in music_tracks:
                yield AppleMusicTrack(music_track, self.library)


class AppleMusicPlaylistFolder(PlaylistFolder):
    def __init__(self, name: str, music_id: int, parent_id: int, library: "AppleMusicLibrary", **_):
        super().__init__(name, [], library)
        self.music_id = music_id
        self.music_parent_id = parent_id


class AppleMusicSmartPlaylist(SmartPlaylist):
    def __init__(self, name: str, music_id: int, parent_id: int, library: "AppleMusicLibrary", **_):
        super().__init__(name, {}, LIBRARY_TYPE, library)
        self.music_id = music_id
        self.music_parent_id = parent_id

    @property
    def tracks(self) -> Iterable[Track]:
        try:
            music_tracks = self.library._track_scpt.call("playlistTracks", self.music_id)
        except applescript.ScriptError as e:
            log.warning("failed on `playlistTracks` script", e=e, name=self.name)
        else:
            for music_track in music_tracks:
                yield AppleMusicTrack(music_track, self.library)


class AppleMusicLibrary(Library):
    def __init__(self, music_root: Path, music_mount: str):
        super().__init__("Apple Music", LIBRARY_TYPE, music_root)
        with importlib.resources.path("resources", "list_playlists.applescript") as fpath:
            self._playlist_scpt = applescript.AppleScript(path=str(fpath))
        with importlib.resources.path("resources", "list_tracks.applescript") as fpath:
            self._track_scpt = applescript.AppleScript(path=str(fpath))
        if music_mount:
            with importlib.resources.path("resources", "volumes.applescript") as fpath:
                self._volumes_scpt = applescript.AppleScript(path=str(fpath))
            self._volumes_scpt.call("mountMusic", music_mount)
            atexit.register(self.eject)
        self._playlist_for = {}
        self._track_for = {}

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def eject(self) -> None:
        if hasattr(self, "_volumes_scpt"):
            message = self._volumes_scpt.call("unmountMusic")
            log.info("message from `unmountMusic", message=message)

    @cached_property
    def playlists(self) -> list[NamedPlaylist]:
        for folder_playlist in self._playlist_scpt.call("listFolderPlaylists"):
            music_id = folder_playlist["music_id"]
            self._playlist_for[music_id] = AppleMusicPlaylistFolder(library=self, **folder_playlist)
        for plain_playlist in self._playlist_scpt.call("listPlaylists"):
            music_id = plain_playlist["music_id"]
            self._playlist_for[music_id] = AppleMusicPlaylist(library=self, **plain_playlist)
        for smart_playlists in self._playlist_scpt.call("listSmartPlaylists"):
            music_id = smart_playlists["music_id"]
            self._playlist_for[music_id] = AppleMusicSmartPlaylist(library=self, **smart_playlists)
        for playlist in self._playlist_for.values():
            if playlist.music_parent_id != -1:
                parent_playlist: PlaylistFolder = self._playlist_for[playlist.music_parent_id]
                parent_playlist.sub_playlists.append(playlist)
        return list(self._playlist_for.values())

    @property
    def tracks(self) -> Iterable[Track]:
        for music_track in self._track_scpt.call("allTracks"):
            yield AppleMusicTrack(music_track, self)


def load_library(apple_music_config: dict[str, Any]) -> AppleMusicLibrary:
    return AppleMusicLibrary(apple_music_config["music_root"], apple_music_config.get("music_mount"))
