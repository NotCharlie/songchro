from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import List

from plexapi import playlist, audio
from plexapi.library import MusicSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from songchro import model


@dataclass
class PlexTrack(model.Track):
    plex_track: audio.Track


class PlexPlaylist(model.Playlist):
    def __init__(self, plex_playlist: playlist.Playlist):
        self.plex_playlist = plex_playlist
        self.name = plex_playlist.title
        self.sub_playlists = []

    @cached_property
    def tracks(self) -> List[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(track.locations[0]),
                album_artist=track.album().artist().title,
            )
            for track in self.plex_playlist.items()
        ]


class PlexLibrary(model.Library):
    def __init__(self, music: MusicSection):
        self.music = music

    @cached_property
    def tracks(self) -> List[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(track.locations[0]),
                album_artist=track.album().artist().title,
            )
            for track in self.music.searchTracks()
        ]

    @cached_property
    def playlists(self) -> List[model.Playlist]:
        return [PlexPlaylist(pl) for pl in self.music.playlists()]

    def find_tracks(self, track: model.Track) -> List[model.Track]:

        def matches(plex_track: model.Track) -> bool:
            artist_match = not track.artist or (track.artist == plex_track.artist)
            album_artist_match = not track.album_artist or (
                track.album_artist == plex_track.album_artist
            )
            name_match = not track.name or (track.name == plex_track.name)
            album_match = not track.album or (track.album == plex_track.album)
            return (artist_match or album_artist_match) and name_match and album_match

        return [plex_track for plex_track in self.tracks if matches(plex_track)]


def load_library_by_username(
    username, password, code, server, section="Music"
) -> PlexLibrary:
    account = MyPlexAccount(username, password, code=code)
    plex = account.resource(server).connect()
    return load_library(plex, section=section)


def load_library_by_baseurl(baseurl, token, section="Music"):
    plex = PlexServer(baseurl, token)
    return load_library(plex, section=section)


def load_library(plex: PlexServer = None, section="Music") -> PlexLibrary:
    plex = plex if plex else PlexServer()
    return PlexLibrary(music=plex.library.section(section))
