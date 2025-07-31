import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterable, Dict, Any


@dataclass(kw_only=True)
class Track:
    """Represent a single song track."""

    name: str = None
    artist: str = None
    album: str = None
    album_artist: str = None
    disc_number: int | None = None
    track_number: int | None = None
    filepath: Path | str | None = None

    def json_data(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "disc_number": self.disc_number,
            "track_number": self.track_number,
            "filepath": self.filepath.as_posix() if self.filepath else None,
        }
        return {key: value for key, value in data.items() if value}

    def to_json(self) -> str:
        return json.dumps(self.json_data())


class Playlist:
    """Represent a playlist."""

    def __init__(self, name: str, tracks: List[Track] = None):
        self.name = name
        self._tracks: List[Track] = tracks if tracks is not None else []

    def json_data(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [track.json_data() for track in self.tracks],
        }

    def to_json(self) -> str:
        return json.dumps(self.json_data(), indent=2)

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks


class PlaylistFolder(Playlist):
    def __init__(self, name: str, sub_playlists: List[Playlist]):
        super().__init__(name)
        self.sub_playlists = sub_playlists

    def json_data(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sub_playlists": [playlist.name for playlist in self.sub_playlists],
        }

    @property
    def tracks(self) -> Iterable[Track]:
        return itertools.chain.from_iterable(
            playlist.tracks for playlist in self.sub_playlists
        )


class SmartPlaylist(Playlist):
    def __init__(self, name: str, smart_criteria):
        super().__init__(name)
        self.smart_criteria = smart_criteria

    def json_data(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "smart_criteria": self.smart_criteria,
        }

    @property
    def tracks(self) -> Iterable[Track]:
        raise NotImplementedError()


@dataclass
class Library:
    """Represent a library of songs."""

    tracks: List[Track]
    playlists: List[Playlist]

    def json_data(self) -> Dict[str, Any]:
        data = {
            "tracks": [track.json_data() for track in self.tracks],
            "playlists": [playlist.json_data() for playlist in self.playlists],
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data())

    def find_tracks(self, track: Track) -> List[Track]:
        raise NotImplementedError()

    def create_playlist(
        self, playlist_name: str, tracks: List[Track], dry_run=False
    ) -> Playlist:
        raise NotImplementedError()

    def find_playlist(self, playlist_name: str) -> Playlist | None:
        playlists = (pl for pl in self.playlists if pl.name == playlist_name)
        playlist = next(playlists, None)
        return playlist
