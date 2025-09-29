import os
import plistlib
import unicodedata
from functools import cached_property
from pathlib import Path
from typing import Any, Self, Iterable, Iterator
from urllib.parse import urlparse, unquote

import structlog

from songchro.model import (
    Library,
    Track,
    Playlist,
    SmartPlaylist,
    PlaylistFolder,
    NamedPlaylist,
    NoSuchTrack,
)

LIBRARY_TYPE = "itunes"

log = structlog.get_logger()


class ItunesTrack(Track):
    def __init__(
        self, track: dict[str, Any], music_root: str, library: "ItunesLibrary"
    ):
        self.itunes_track = track
        location = track.get("Location", None)
        parsed = urlparse(location)
        path = unquote(parsed.path) if parsed.path else None
        filepath = Path(os.path.relpath(path, start=music_root)) if path else None

        super().__init__(
            name=track["Name"],
            artist=track.get("Artist", None),
            album=track.get("Album", None),
            album_artist=track.get("Album Artist", None),
            disc_number=track.get("Disc Number", 1),
            track_number=track.get("Track Number", None),
            filepath=filepath,
            playcounts={LIBRARY_TYPE: track.get("Play Count", 0)},
            library=library,
        )

    def key(self):
        return self.itunes_track["Track ID"]

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, ItunesTrack):
            return self.key() == other.key()
        return NotImplemented

    def increment_plays(self, increase):
        log.info(
            "attempting to increment_plays, not supported",
            increase=increase,
            cls=self.__class__,
        )


class ItunesPlaylist(Playlist):
    def __init__(
        self,
        name: str,
        tracks: list[ItunesTrack],
        itunes_playlist: dict[str, Any],
        library: "ItunesLibrary",
    ):
        super().__init__(name, library, tracks=tracks)
        self.itunes_playlist = itunes_playlist

    def sync_tracks(self, other: NamedPlaylist, /, dry_run=False):
        super().sync_tracks(other, dry_run=dry_run)


class ItunesSmartPlaylist(SmartPlaylist):
    def __init__(
        self,
        name: str,
        itunes_criteria,
        itunes_playlist: dict,
        tracks: list[Track],
        library: "ItunesLibrary",
    ):
        super().__init__(name, {}, LIBRARY_TYPE, library)
        self._tracks = tracks
        self.itunes_playlist = itunes_playlist
        self.itunes_criteria = itunes_criteria

    @property
    def tracks(self) -> Iterable[Track]:
        return self._tracks


class ItunesPlaylistFolder(PlaylistFolder):
    def __init__(
        self,
        name: str,
        sub_playlists: list[ItunesPlaylist | ItunesSmartPlaylist | Self],
        itunes_playlist: dict[str, Any],
        library: "ItunesLibrary",
    ):
        super().__init__(name, sub_playlists, library)
        self.itunes_playlist = itunes_playlist


class ItunesLibrary(Library):
    def __init__(
        self,
        music_root: Path,
        itunes_library: dict[str, Any],
        xml_path: str,
    ):
        super().__init__("iTunes", LIBRARY_TYPE, music_root)
        self.itunes_library = itunes_library
        self.xml_path = xml_path

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.xml_path}"

    @cached_property
    def track_for_id(self) -> dict[str, ItunesTrack]:
        result: dict[str, ItunesTrack] = {}
        for track in self.itunes_library["Tracks"].values():
            track_id = track["Track ID"]
            itunes_track = ItunesTrack(track, str(self.music_root), self)
            result[str(track_id)] = itunes_track
        return result

    @cached_property
    def track_for_path(self) -> dict[str, ItunesTrack]:
        return {
            unicodedata.normalize("NFC", str(track.filepath)): track
            for track in self.track_for_id.values()
        }

    def _find_track_for_path(self, fpath: str) -> ItunesTrack:
        return self.track_for_path.get(unicodedata.normalize("NFC", fpath))

    def map_tracks(
        self, tracks: Iterable[Track], /, dry_run: bool = False
    ) -> Iterator[Track]:
        for track in tracks:
            if track.filepath:
                yield self._find_track_for_path(str(track.filepath))
            else:
                if dry_run:
                    log.warning(
                        "no track for path", filepath=track.filepath, track=track
                    )
                else:
                    raise NoSuchTrack(track.filepath)

    @cached_property
    def tracks(self) -> list[ItunesTrack]:
        return list(self.track_for_id.values())

    @cached_property
    def playlists(self) -> list[NamedPlaylist]:
        result: dict[
            str, ItunesPlaylist | ItunesSmartPlaylist | ItunesPlaylistFolder
        ] = {}
        for playlist in self.itunes_library["Playlists"]:
            if not playlist.get("Visible", True):
                continue
            if playlist.get("Distinguished Kind", None):
                continue

            playlist_tracks = []
            for playlist_item in playlist.get("Playlist Items", []):
                track_id = playlist_item["Track ID"]
                playlist_tracks.append(self.track_for_id[str(track_id)])

            if playlist.get("Folder", False):
                itunes_playlist = ItunesPlaylistFolder(
                    name=playlist["Name"],
                    sub_playlists=[],
                    itunes_playlist=playlist,
                    library=self,
                )
            elif playlist.get("Smart Info", None):
                itunes_playlist = ItunesSmartPlaylist(
                    name=playlist["Name"],
                    library=self,
                    itunes_criteria=playlist["Smart Info"],
                    itunes_playlist=playlist,
                    tracks=playlist_tracks,
                )
            else:
                itunes_playlist = ItunesPlaylist(
                    itunes_playlist=playlist,
                    name=playlist["Name"],
                    tracks=playlist_tracks,
                    library=self,
                )
            result[playlist["Playlist Persistent ID"]] = itunes_playlist

        # Update sub_playlists
        for key, playlist in result.items():
            parent_id: str | None = playlist.itunes_playlist.get(
                "Parent Persistent ID", None
            )
            if parent_id:
                parent_playlist = result[parent_id]
                assert (
                    type(parent_playlist) is ItunesPlaylistFolder
                ), f"{parent_id} is not an ItunesPlaylistFolder"
                parent_playlist.sub_playlists.append(playlist)
        return list(result.values())

    def find_track(self, track: Track) -> list[Track]:
        track = self._find_track_for_path(track.filepath)
        return [track] if track else []


def load_library(xml: str, music_root: str) -> ItunesLibrary:
    """Load an iTunes library."""
    with open(xml, "rb") as f:
        library = plistlib.load(f)
        return ItunesLibrary(
            itunes_library=library,
            music_root=Path(music_root),
            xml_path=xml,
        )
