from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

from plexapi.playlist import Playlist


@dataclass
class Track:
    """Represent a single song track."""

    name: str
    artist: str
    album: str
    album_artist: str
    filepath: Path


@dataclass
class Playlist:
    """Represent a playlist."""

    name: str
    tracks: List[Track]
    sub_playlists: List[Playlist]
    parent_playlist: Union[Playlist, None]


@dataclass
class Library:
    """Represent a library of songs."""

    tracks: List[Track]
    playlists: List[Playlist]
