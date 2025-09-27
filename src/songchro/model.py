import itertools
import unicodedata
from collections.abc import Iterable, Callable, Iterator
from dataclasses import dataclass
from json import JSONEncoder
from pathlib import Path
from typing import Any, Protocol

import structlog
from multimethod import multimethod

log = structlog.get_logger()


class SongchroException(Exception):
    pass


class InvalidSyncError(SongchroException):
    def __init__(self, target: type, source: type):
        super().__init__(f"Cannot sync to {target.__name__} from {source.__name__}")
        self.target = target
        self.source = source


class CanAddItem(Protocol):
    def add_item(self, track: "Track", after: "Track") -> None:
        raise NotImplementedError


class TracksSyncer:
    def sync(
        self: CanAddItem,
        my_tracks: Iterable["Track"],
        other: Iterable["Track"],
        mapper: Callable[[Iterable["Track"]], Iterator["Track"]],
        /,
        dry_run=False,
    ) -> bool:
        changed = False
        (my_iter_iter, remaining_tracks_iter) = itertools.tee(my_tracks)

        # assuming that each track is in a playlist only once
        remaining_tracks = {t.key() for t in remaining_tracks_iter}
        my_iter = enumerate(my_iter_iter)
        add_after = None
        my_idx, my_next_track = next(my_iter, (-1, None))
        other_iter = enumerate(mapper(other))
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
                    self.add_item(next_other, add_after)
                add_after = next_other
                other_idx, next_other = next(other_iter, (-1, None))
        return changed


class HasJsonDataEncoder(JSONEncoder):
    def default(self, o):
        if hasattr(o, "json_data"):
            return o.json_data()
        return super().default(o)


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
    playcounts: dict[str, int] = None
    library: "Library" = None

    def json_data(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "disc_number": self.disc_number,
            "track_number": self.track_number,
            "filepath": Path(self.filepath).as_posix() if self.filepath else None,
            "playcounts": self.playcounts,
        }
        return {key: value for key, value in data.items() if value}

    def key(self):
        return unicodedata.normalize("NFC", str(self.filepath))

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, Track):
            return self.key() == other.key()
        return NotImplemented

    def increment_plays(self, increase):
        self.playcounts[self.library.lib_type] += increase


class NamedPlaylist:
    def __init__(self, name: str, library: "Library"):
        self.name = name
        self.library = library

    @property
    def tracks(self) -> Iterable[Track]:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not contain tracks directly"
        )

    def sync_tracks(self, other: "NamedPlaylist", /, dry_run=False) -> bool:
        raise InvalidSyncError(self.__class__, other.__class__)

    def json_data(self):
        return {
            "name": self.name,
        }


class Playlist(NamedPlaylist, TracksSyncer):
    """Represent a playlist."""

    def __init__(self, name: str, library: "Library", /, tracks: list[Track] = None):
        super().__init__(name, library)
        self._tracks: list[Track] = tracks if tracks is not None else []

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [track.json_data() for track in self.tracks],
        }

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks

    def sync_tracks(self, other: NamedPlaylist, /, dry_run=False) -> bool:
        return self.sync(
            self.tracks, other.tracks, self.library.map_tracks, dry_run=dry_run
        )

    def add_item(self, track: Track, after: Track):
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

    @multimethod
    def sync_tracks(self, other: Playlist, /, dry_run=False) -> bool:
        return super().sync_tracks(other, dry_run=dry_run)

    @multimethod
    def sync_tracks(self, other: "PlaylistFolder", /, dry_run=False) -> bool:
        orig_len = len(self.sub_playlists)
        sub_playlists = {p.name for p in self.sub_playlists}
        sub_playlists.update({o.name for o in other.sub_playlists})
        self.sub_playlists = [
            self.library.find_playlist(name) for name in sub_playlists
        ]
        return orig_len != len(self.sub_playlists)


class SmartPlaylist(NamedPlaylist):
    def __init__(
        self,
        name: str,
        smart_criteria: dict[str, Any],
        criteria_key: str,
        library: "Library",
    ):
        super().__init__(name, library)
        self.smart_criteria = smart_criteria
        self.criteria_key = criteria_key

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "smart_criteria": self.smart_criteria,
        }

    def _filter(self) -> Callable[[Track], bool]:
        raise NotImplementedError

    @property
    def tracks(self) -> Iterable[Track]:
        if self.criteria_key in self.smart_criteria:
            fn = self._filter()
            return (t for t in self.library.tracks if fn(t))

        log.warning(
            "unable to get `tracks` without criteria",
            name=self.name,
            key=self.criteria_key,
            type=self.__class__.__name__,
        )
        return []


class Library:
    """Represent a library of songs."""

    def __init__(
        self,
        source: str,
        lib_type: str,
        music_root: Path,
        tracks: list[Track] = None,
        playlists: list[Playlist] = None,
    ):
        self.source = source
        self.lib_type = lib_type
        self.music_root = music_root
        self._tracks = tracks if tracks else []
        self._playlists = playlists if playlists else []

    def __str__(self):
        return f"<{self.__class__.__name__} playlists={self.playlists}>"

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks

    @property
    def playlists(self) -> list[NamedPlaylist]:
        return self._playlists

    def json_data(self) -> dict[str, Any]:
        data = {
            "tracks": [track.json_data() for track in self.tracks],
            "playlists": [playlist.json_data() for playlist in self.playlists],
        }
        return data

    def find_track(self, track: Track) -> list[Track]:
        raise NotImplementedError()

    def map_tracks(
        self, tracks: Iterable[Track], /, dry_run: bool = False
    ) -> Iterator[Track]:
        raise NotImplementedError()

    def create_playlist(
        self,
        playlist_name: str,
        source: NamedPlaylist,
        dry_run=False,
    ) -> None:
        raise NotImplementedError()

    def find_playlist(self, playlist_name: str) -> Playlist | None:
        playlists = (pl for pl in self.playlists if pl.name == playlist_name)
        playlist = next(playlists, None)
        return playlist
