import plistlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse, unquote

from songchro.model import Library, Track, Playlist


@dataclass
class ItunesTrack(Track):
    itunes_track: dict = field(repr=False)


@dataclass
class ItunesPlaylist(Playlist):
    itunes_playlist: dict = field(repr=False)


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
            album_artist=track.get("Album Artist", None),
            filepath=filepath,
        )
        tracks[str(track_id)] = itunes_track

    playlists: dict[str, ItunesPlaylist] = {}
    for playlist in library["Playlists"]:
        playlist_tracks = []
        for playlist_item in playlist.get("Playlist Items", []):
            track_id = playlist_item["Track ID"]
            playlist_tracks.append(tracks[str(track_id)])

        itunes_playlist = ItunesPlaylist(
            itunes_playlist=playlist,
            name=playlist["Name"],
            tracks=playlist_tracks,
            sub_playlists=[],
            parent_playlist=None,
        )
        playlists[playlist["Playlist Persistent ID"]] = itunes_playlist

    # Update sub_ & parent_ playlists
    for key, playlist in playlists.items():
        parent_id = playlist.itunes_playlist.get("Parent Persistent ID", None)
        if parent_id:
            parent_playlist = playlists[parent_id]
            parent_playlist.sub_playlists.append(playlist)
            playlist.parent_playlist = parent_playlist

    return ItunesLibrary(
        itunes_library=library,
        tracks=list(tracks.values()),
        playlists=list(playlists.values()),
    )
