from dataclasses import dataclass
from pathlib import Path

from plexapi import playlist, audio
from plexapi.library import MusicSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from songchro import model


@dataclass
class PlexTrack(model.Track):
    plex_track: audio.Track


@dataclass
class PlexPlaylist(model.Playlist):
    plex_playlist: playlist.Playlist


@dataclass
class PlexLibrary(model.Library):
    plex_section: MusicSection


def load_library_by_username(
    username, password, code, server, section="Music"
) -> PlexLibrary:
    account = MyPlexAccount(username, password, code=code)
    plex = account.resource(server).connect()
    return load_library(plex)


def load_library_by_baseurl(baseurl, token, section="Music"):
    plex = PlexServer(baseurl, token)
    return load_library(plex)


def load_library(plex: PlexServer = None, section="Music") -> PlexLibrary:
    plex = plex if plex else PlexServer()
    music: MusicSection = plex.library.section(section)

    tracks = {}
    for track in music.searchTracks():
        plex_track = PlexTrack(
            plex_track=track,
            name=track.title,
            artist=track.artist().title,
            album=track.album().title,
            filepath=Path(track.locations[0]),
            album_artist=track.album().artist().title,
        )
        tracks[track.key] = plex_track

    playlists = []
    for playlist in music.playlists():
        playlist_tracks = []
        for item in playlist.items():
            plex_track = tracks[item.key]
            playlist_tracks.append(plex_track)
        plex_playlist = PlexPlaylist(
            plex_playlist=playlist,
            name=playlist.title,
            tracks=playlist_tracks,
            sub_playlists=[],
            parent_playlist=None,
        )
        playlists.append(plex_playlist)

    return PlexLibrary(
        plex_section=music, playlists=playlists, tracks=list(tracks.values())
    )
