import os
import plistlib
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse, unquote

from songchro.model import Library, Track, Playlist, SmartPlaylist, PlaylistFolder


@dataclass
class ItunesTrack(Track):
    itunes_track: dict = field(repr=False)

    def key(self):
        return unicodedata.normalize("NFC", self.itunes_track["Track ID"])

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, ItunesTrack):
            return self.key() == other.key()
        return NotImplemented


class ItunesPlaylist(Playlist):
    def __init__(
        self,
        name: str,
        tracks: List[ItunesTrack],
        itunes_playlist: Dict,
        library: "ItunesLibrary",
    ):
        super().__init__(name, library, tracks=tracks)
        self.itunes_playlist = itunes_playlist

    def sync_tracks(self, other: "Playlist", /, dry_run=False):
        raise NotImplemented


class ItunesSmartPlaylist(SmartPlaylist):
    def __init__(
        self, name: str, smart_criteria, itunes_playlist: Dict, library: "ItunesLibrary"
    ):
        super().__init__(name, "TODO", library)
        self.itunes_playlist = itunes_playlist
        self.itunes_criteria = smart_criteria


class ItunesPlaylistFolder(PlaylistFolder):
    def __init__(
        self,
        name: str,
        sub_playlists: List[ItunesPlaylist],
        itunes_playlist: Dict,
        library: "ItunesLibrary",
    ):
        super().__init__(name, sub_playlists, library)
        self.itunes_playlist = itunes_playlist


class ItunesLibrary(Library):
    def __init__(
        self,
        music_root: Path,
        itunes_library: Dict,
    ):
        super().__init__(music_root)
        self.itunes_library = itunes_library

    @cached_property
    def track_for(self) -> Dict[str, ItunesTrack]:
        result: Dict[str, ItunesTrack] = {}
        for track in self.itunes_library["Tracks"].values():
            track_id = track["Track ID"]
            location = track.get("Location", None)
            parsed = urlparse(location)
            path = unquote(parsed.path) if parsed.path else None
            filepath = (
                Path(os.path.relpath(path, start=self.music_root)) if path else None
            )
            itunes_track = ItunesTrack(
                itunes_track=track,
                name=track["Name"],
                artist=track.get("Artist", None),
                album=track.get("Album", None),
                album_artist=track.get("Album Artist", track.get("Artist", None)),
                disc_number=track.get("Disc Number", 1),
                track_number=track.get("Track Number", None),
                filepath=filepath,
            )
            result[str(track_id)] = itunes_track
        return result

    @cached_property
    def tracks(self) -> List[ItunesTrack]:
        return list(self.track_for.values())

    @cached_property
    def playlists(self) -> List[Playlist]:
        result: Dict[
            str, ItunesPlaylist | ItunesSmartPlaylist | ItunesPlaylistFolder
        ] = {}
        for playlist in self.itunes_library["Playlists"]:
            if not playlist.get("Visible", True):
                continue
            if playlist.get("Distinguished Kind", None):
                continue

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
                    smart_criteria=playlist["Smart Info"],
                    itunes_playlist=playlist,
                )
            else:
                playlist_tracks = []
                for playlist_item in playlist.get("Playlist Items", []):
                    track_id = playlist_item["Track ID"]
                    playlist_tracks.append(self.track_for[str(track_id)])

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


def load_library(xml: str, music_root: str) -> ItunesLibrary:
    """Load an iTunes library."""
    with open(xml, "rb") as f:
        library = plistlib.load(f)
        return ItunesLibrary(
            itunes_library=library,
            music_root=Path(music_root),
        )
