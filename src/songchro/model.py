import itertools
import json
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    def json_data(self) -> dict[str, Any]:
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


class NamedPlaylist:
    def __init__(self, name: str, library: "Library"):
        self.name = name
        self.library = library

    @property
    def tracks(self) -> Iterable[Track]:
        raise NotImplementedError()

    def sync_tracks(self, other: "NamedPlaylist", /, dry_run=False):
        raise RuntimeError(
            f"cannot directly sync tracks into {self.__class__.__name__}"
        )


class Playlist(NamedPlaylist):
    """Represent a playlist."""

    def __init__(self, name: str, library: "Library", /, tracks: list[Track] = None):
        super().__init__(name, library)
        self._tracks: list[Track] = tracks if tracks is not None else []

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [track.json_data() for track in self.tracks],
        }

    def to_json(self) -> str:
        return json.dumps(self.json_data(), indent=2)

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks

    def sync_tracks(self, other: "Playlist", /, dry_run=False) -> bool:
        changed = False
        # assuming that each track is in a playlist only once
        remaining_tracks = {t.key() for t in self.tracks}
        my_iter = enumerate(self.tracks)
        add_after = None
        my_idx, my_next_track = next(my_iter, (-1, None))
        other_iter = enumerate(self.library.map_tracks(other.tracks))
        other_idx, next_other = next(other_iter, (-1, None))
        while next_other:
            log.debug(
                "checking next track",
                other_idx=other_idx,
                next_other=next_other,
                my_idx=my_idx,
                my_next_track=my_next_track,
            )
            if next_other == my_next_track:
                add_after = my_next_track
                remaining_tracks.remove(my_next_track.key())
                my_idx, my_next_track = next(my_iter, (-1, None))
                other_idx, next_other = next(other_iter, (-1, None))
            elif next_other.key() in remaining_tracks:
                while next_other != my_next_track:
                    log.debug(
                        "looking for other",
                        my_next_track=my_next_track,
                        next_other=next_other,
                    )
                    remaining_tracks.remove(my_next_track.key())
                    add_after = my_next_track
                    my_idx, my_next_track = next(my_iter, (-1, None))
                    assert my_next_track
            else:
                log.info(
                    f"inserting track",
                    other_idx=other_idx,
                    next_other=next_other,
                    my_idx=my_idx,
                    add_after=add_after,
                    dry_run=dry_run,
                )
                changed = True
                if not dry_run:
                    self._add_item(next_other, add_after)
                add_after = next_other
                other_idx, next_other = next(other_iter, (-1, None))
        return changed

    def _add_item(self, track: Track, after: Track):
        if after:
            idx = self._tracks.index(after)
            self._tracks.insert(idx + 1, track)
        else:
            self._tracks.append(track)

    def __str__(self):
        return (
            f"{self.__class__.__name__} '{self.name}' ({len(list(self.tracks))} tracks)"
        )


class PlaylistFolder(NamedPlaylist):
    def __init__(
        self, name: str, sub_playlists: list[NamedPlaylist], library: "Library"
    ):
        super().__init__(name, library)
        self.sub_playlists = sub_playlists

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sub_playlists": [playlist.name for playlist in self.sub_playlists],
        }

    @property
    def tracks(self) -> Iterable[Track]:
        return itertools.chain.from_iterable(
            playlist.tracks for playlist in self.sub_playlists
        )


class SmartPlaylist(NamedPlaylist):
    def __init__(self, name: str, smart_criteria, library: "Library"):
        super().__init__(name, library)
        self.smart_criteria = smart_criteria

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "smart_criteria": self.smart_criteria,
        }


class Library:
    """Represent a library of songs."""

    def __init__(
        self,
        source: str,
        music_root: Path,
        tracks: list[Track] = None,
        playlists: list[Playlist] = None,
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
    def playlists(self) -> list[Playlist]:
        return self._playlists

    def json_data(self) -> dict[str, Any]:
        data = {
            "tracks": [track.json_data() for track in self.tracks],
            "playlists": [playlist.json_data() for playlist in self.playlists],
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.json_data(), indent=2)

    def find_track(self, track: Track) -> list[Track]:
        raise NotImplementedError()

    def map_tracks(
        self, tracks: Iterable[Track], /, dry_run: bool = False
    ) -> list[Track]:
        raise NotImplementedError()

    def create_playlist(
        self, playlist_name: str, tracks: Iterable[Track], dry_run=False
    ) -> None:
        raise NotImplementedError()

    def find_playlist(self, playlist_name: str) -> Playlist | None:
        playlists = (pl for pl in self.playlists if pl.name == playlist_name)
        playlist = next(playlists, None)
        return playlist
