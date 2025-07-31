import plistlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import urlparse, unquote

from songchro.model import Library, Track, Playlist, SmartPlaylist, PlaylistFolder


@dataclass
class ItunesTrack(Track):
    itunes_track: dict = field(repr=False)


class ItunesPlaylist(Playlist):
    def __init__(self, name: str, tracks: List[ItunesTrack], itunes_playlist: Dict):
        super().__init__(name, tracks=tracks)
        self.itunes_playlist = itunes_playlist


class ItunesSmartPlaylist(SmartPlaylist):
    def __init__(self, name: str, smart_criteria, itunes_playlist: Dict):
        super().__init__(name, "TODO")
        self.itunes_playlist = itunes_playlist
        self.itunes_criteria = smart_criteria


class ItunesPlaylistFolder(PlaylistFolder):
    def __init__(
        self, name: str, sub_playlists: List[ItunesPlaylist], itunes_playlist: Dict
    ):
        super().__init__(name, sub_playlists)
        self.itunes_playlist = itunes_playlist


@dataclass
class ItunesLibrary(Library):
    itunes_library: dict = field(repr=False)


def load_library(xml: str) -> ItunesLibrary:
    """Load an iTunes library."""
    with open(xml, "rb") as f:
        library = plistlib.load(f)

    tracks: dict[str, ItunesTrack] = {}
    for track in library["Tracks"].values():
        track_id = track["Track ID"]
        location = track.get("Location", None)
        parsed = urlparse(location)
        path = unquote(parsed.path) if parsed.path else None
        filepath = Path(path) if path else None
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
        tracks[str(track_id)] = itunes_track

    playlists: Dict[
        str, ItunesPlaylist | ItunesSmartPlaylist | ItunesPlaylistFolder
    ] = {}
    for playlist in library["Playlists"]:
        if not playlist.get("Visible", True):
            continue
        if playlist.get("Distinguished Kind", None):
            continue

        if playlist.get("Folder", False):
            itunes_playlist = ItunesPlaylistFolder(
                name=playlist["Name"], sub_playlists=[], itunes_playlist=playlist
            )
        elif playlist.get("Smart Info", None):
            itunes_playlist = ItunesSmartPlaylist(
                name=playlist["Name"],
                smart_criteria=playlist["Smart Info"],
                itunes_playlist=playlist,
            )
        else:
            playlist_tracks = []
            for playlist_item in playlist.get("Playlist Items", []):
                track_id = playlist_item["Track ID"]
                playlist_tracks.append(tracks[str(track_id)])

            itunes_playlist = ItunesPlaylist(
                itunes_playlist=playlist,
                name=playlist["Name"],
                tracks=playlist_tracks,
            )
        playlists[playlist["Playlist Persistent ID"]] = itunes_playlist

    # Update sub_playlists
    for key, playlist in playlists.items():
        parent_id: str | None = playlist.itunes_playlist.get(
            "Parent Persistent ID", None
        )
        if parent_id:
            parent_playlist = playlists[parent_id]
            assert (
                type(parent_playlist) is ItunesPlaylistFolder
            ), f"{parent_id} is not an ItunesPlaylistFolder"
            parent_playlist.sub_playlists.append(playlist)

    return ItunesLibrary(
        itunes_library=library,
        tracks=list(tracks.values()),
        playlists=list(playlists.values()),
    )
