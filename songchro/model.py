import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Union

import click
from plexapi.playlist import Playlist


@dataclass
class Track:
    """Represent a single song track."""

    name: str
    artist: str
    album: str
    album_artist: str
    filepath: Path | None

    def json_data(self) -> dict:
        data = {
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "filepath": self.filepath.as_posix(),
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data())


@dataclass
class Playlist:
    """Represent a playlist."""

    name: str
    tracks: List[Track]
    sub_playlists: List[Playlist]
    parent_playlist: Playlist | None = field(repr=False)

    def json_data(self):
        data = {
            "name": self.name,
            "tracks": [track.json_data() for track in self.tracks],
            "sub_playlists": [
                sub_playlist.json_data() for sub_playlist in self.sub_playlists
            ],
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data())


@dataclass
class Library:
    """Represent a library of songs."""

    tracks: List[Track]
    playlists: List[Playlist]

    def json_data(self) -> dict:
        data = {
            "tracks": [track.json_data() for track in self.tracks],
            "playlists": [playlist.json_data() for playlist in self.playlists],
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data())

    def find_playlist(self, playlist_name: str) -> Playlist | None:
        playlists = (pl for pl in self.playlists if pl.name == playlist_name)
        playlist = next(playlists, None)
        return playlist
