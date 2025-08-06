import itertools
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterable, Dict, Any

import structlog

log = structlog.get_logger()


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
            "filepath": Path(self.filepath).as_posix() if self.filepath else None,
        }
        return {key: value for key, value in data.items() if value}

    def to_json(self) -> str:
        return json.dumps(self.json_data())

    def key(self):
        return unicodedata.normalize("NFC", str(self.filepath))

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, Track):
            return self.key() == other.key()
        return NotImplemented


class Playlist:
    """Represent a playlist."""

    def __init__(self, name: str, library: "Library", /, tracks: List[Track] = None):
        self.name = name
        self._tracks: List[Track] = tracks if tracks is not None else []
        self.library = library

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

    def sync_tracks(self, other: "Playlist", /, dry_run=False):
        my_tracks = {track.key(): track for track in self.tracks}
        other_tracks = {
            track.key(): track for track in self.library.map_tracks(other.tracks)
        }
        combined_tracks = other_tracks | my_tracks
        log.info(f"combined tracks", count=len(combined_tracks))

        my_iter = (track for track in my_tracks.values())
        add_after = None
        my_next_track = next(my_iter, None)
        combined_iter = enumerate(combined_tracks.values())
        idx, combined_track = next(combined_iter, (-1, None))
        while combined_track or my_next_track:
            if combined_track == my_next_track:
                log.debug(
                    "tracks match",
                    combined_track=combined_track,
                    my_next_track=my_next_track,
                )
                add_after = my_next_track
                my_next_track = next(my_iter, None)
                idx, combined_track = next(combined_iter, (-1, None))
            elif combined_track:
                log.info(
                    f"inserting track",
                    idx=idx,
                    combined_track=combined_track,
                    add_after=add_after,
                    dry_run=dry_run,
                )
                if not dry_run:
                    self._add_item(combined_track, add_after)
                add_after = combined_track
                idx, combined_track = next(combined_iter, (-1, None))
            else:
                log.debug("reached end of combined_tracks")
                break

    def _add_item(self, track: Track, after):
        if after:
            idx = self._tracks.index(after)
            self._tracks.insert(idx + 1, track)
        else:
            self._tracks.append(track)

    def __str__(self):
        return (
            f"{self.__class__.__name__} '{self.name}' ({len(list(self.tracks))} tracks)"
        )


class PlaylistFolder(Playlist):
    def __init__(self, name: str, sub_playlists: List[Playlist], library: "Library"):
        super().__init__(name, library)
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

    def sync_tracks(self, other: Playlist, /, dry_run=False):
        raise RuntimeError(
            f"cannot directly sync tracks into {self.__class__.__name__}"
        )


class PlaylistName(Playlist):
    def __init__(self, name: str, library: "Library"):
        super().__init__(name, library)

    def sync_tracks(self, other: Playlist, /, dry_run=False):
        raise RuntimeError(
            f"cannot directly sync tracks into {self.__class__.__name__}"
        )


class SmartPlaylist(Playlist):
    def __init__(self, name: str, smart_criteria, library: "Library"):
        super().__init__(name, library)
        self.smart_criteria = smart_criteria

    def json_data(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "smart_criteria": self.smart_criteria,
        }

    @property
    def tracks(self) -> Iterable[Track]:
        raise NotImplementedError()

    def sync_tracks(self, other: Playlist, /, dry_run=False):
        raise RuntimeError(
            f"cannot directly sync tracks into {self.__class__.__name__}"
        )


class Library:
    """Represent a library of songs."""

    def __init__(
        self,
        source: str,
        music_root: Path,
        tracks: List[Track] = None,
        playlists: List[Playlist] = None,
    ):
        self.source = source
        self.music_root = music_root
        self._tracks = tracks if tracks else []
        self._playlists = playlists if playlists else []

    def __str__(self):
        return f"<{self.__class__.__name__} playlists={self.playlists}>"

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks

    @property
    def playlists(self) -> List[Playlist]:
        return self._playlists

    def json_data(self) -> Dict[str, Any]:
        data = {
            "tracks": [track.json_data() for track in self.tracks],
            "playlists": [playlist.json_data() for playlist in self.playlists],
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data(), indent=2)

    def find_track(self, track: Track) -> List[Track]:
        raise NotImplementedError()

    def map_tracks(
        self, tracks: Iterable[Track], /, dry_run: bool = False
    ) -> List[Track]:
        raise NotImplementedError()

    def create_playlist(
        self, playlist_name: str, tracks: Iterable[Track], dry_run=False
    ) -> None:
        raise NotImplementedError()

    def find_playlist(self, playlist_name: str) -> Playlist | None:
        playlists = (pl for pl in self.playlists if pl.name == playlist_name)
        playlist = next(playlists, None)
        return playlist
