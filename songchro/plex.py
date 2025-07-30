import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import List, Set, Dict, Any, Iterable

from plexapi import playlist, audio
from plexapi.exceptions import NotFound
from plexapi.library import MusicSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from songchro import model

import structlog

log = structlog.get_logger()


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
                disc_number=track.parentIndex,
                track_number=track.index,
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

    @staticmethod
    def _perform_replacements(input: str) -> Set[str]:
        if not input:
            return set()
        result = {input}
        processed = set()
        queue = [input]

        subs = {
            "-": "‐",
            "‐": "–",
            "''": '"',
            "'": "’",
            "`": "'",
            '"': "",
            " / ": "/",
            " A ": " a ",
            " The ": " the ",
            " An ": " an ",
            " Of ": " of ",
            " On ": " on ",
            " & ": " and ",
            " And ": " and ",
            " and ": " & ",
            " With ": " with ",
            " In ": " in ",
            "?": "",
            "...": "…",
            ".": "",
            ",": "",
            " No.": " no.",
        }
        while queue:
            element = queue.pop(0)
            for sub, replacement in subs.items():
                if sub in element:
                    new_element = element.replace(sub, replacement)
                    if new_element not in result:
                        result.add(new_element)
                        if new_element not in processed:
                            processed.add(new_element)
                            queue.append(new_element)
        return result

    @staticmethod
    def _strip_regexes(input: str):
        if not input:
            yield ""
            return
        processed = set()
        queue = [input]
        regexes = [
            (re.compile(r" \(.*?\)$"), ""),
            (re.compile(r" \[.*?]$"), ""),
            (re.compile(r" - .*?$"), ""),
            (re.compile(r" EP$"), ""),
            (re.compile(r" Soundtrack$"), ""),
            (re.compile(r" OST$"), ""),
            (re.compile(r"^.*?: "), ""),
            (re.compile(r"^\(.*?\) "), ""),
            (re.compile(r"\((.*?)\)$"), r"\g<1>"),
        ]
        while queue:
            element = queue.pop(0)
            yield element
            for regex, replacement in regexes:
                match = regex.search(element)
                if match:
                    new_element = re.sub(regex, replacement, element)
                    if new_element not in processed:
                        processed.add(new_element)
                        queue.append(new_element)

    @staticmethod
    def _make_filter(elements: Dict[str, Iterable[str]]) -> Dict[str, Any]:
        return {
            "and": [
                {"or": [{key: element} for element in values if element]}
                for key, values in elements.items()
            ]
        }

    def _find_tightest_match(self, to_find: model.Track) -> List[audio.Track]:
        tightest_match = []
        log.debug("start _find_tightest_match", to_find=to_find)
        for title in self._strip_regexes(to_find.name):
            log.debug("using title", title=title)
            for album_title in self._strip_regexes(to_find.album):
                log.debug("using album_title", album_title=album_title)
                subqueries = {
                    "title": self._perform_replacements(title),
                    "album.title": self._perform_replacements(album_title),
                    "artist.title": [
                        *self._perform_replacements(to_find.artist),
                        *self._perform_replacements(to_find.album_artist),
                    ],
                    "track.index": (to_find.track_number,),
                }
                subqueries["title="] = subqueries["title"]
                subqueries["album.title="] = subqueries["album.title"]
                combos = [
                    (
                        [
                            "title=",
                            "album.title=",
                            "artist.title",
                            "track.index",
                        ],
                        None,
                    ),
                    (
                        [
                            "title",
                            "album.title",
                            "artist.title",
                            "track.index",
                        ],
                        None,
                    ),
                    (["title=", "album.title=", "track.index"], None),
                    (["title", "album.title", "track.index"], None),
                    (["album.title=", "track.index"], None),
                    (["album.title", "track.index"], None),
                    (["title=", "track.index"], None),
                    (["title", "track.index"], None),
                    (["title=", "album.title"], None),
                    (["title", "album.title"], None),
                    (["title=", "artist.title"], None),
                    (["title", "artist.title"], None),
                    (
                        [
                            "title=",
                        ],
                        lambda track: track.album().artist().title
                        == to_find.album_artist,
                    ),
                ]
                for fields, fn in combos:
                    log.debug("performing query", fields=fields)
                    query = self._make_filter({key: subqueries[key] for key in fields})
                    tracks = [
                        track
                        for track in self.music.searchTracks(filters=query)
                        if track.parentIndex == to_find.disc_number
                        or not to_find.disc_number
                    ]
                    log.debug("resulting tracks", tracks=tracks)
                    if fn:
                        tracks = list(filter(fn, tracks))
                    if tracks:
                        if len(tracks) == 1:
                            log.debug("track found", tracks=tracks)
                            return tracks
                        if tightest_match:
                            if len(tracks) < len(tightest_match):
                                log.debug(
                                    f"new tighest match", tracks=tracks, query=query
                                )
                                tightest_match = tracks
                        else:
                            log.debug(
                                f"initial tightest match", tracks=tracks, query=query
                            )
                            tightest_match = tracks
        return tightest_match

    def find_tracks(self, to_find: model.Track) -> List[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(track.locations[0]),
                album_artist=track.album().artist().title,
                track_number=track.trackNumber,
                disc_number=track.parentIndex,
            )
            for track in self._find_tightest_match(to_find)
        ]

    def create_playlist(
        self, playlist_name: str, tracks: List[model.Track], dry_run=False
    ) -> model.Playlist | None:
        errors = []
        if not dry_run:
            try:
                self.music.playlist(playlist_name)
                return None
            except NotFound:
                pass  # expected case
        plex_tracks = []
        for track in tracks:
            plex_track = self.find_tracks(track)
            if len(plex_track) != 1:
                msg = f"Found {len(plex_track)} tracks for {track}"
                if dry_run:
                    errors.append(msg)
                else:
                    raise RuntimeError(msg)
            else:
                plex_tracks.append(plex_track[0])
        if not errors and not dry_run:
            playlist = self.music.createPlaylist(
                playlist_name, [tr.plex_track for tr in plex_tracks]
            )
            return PlexPlaylist(playlist)
        print(f"Found {len(errors)} errors")
        for index, error in enumerate(errors):
            print(f"  {index+1}. {error}")
        return None


def load_library_by_username(
    username, password, code, server, section="Music"
) -> PlexLibrary:
    account = MyPlexAccount(username, password, code=code)
    plex = account.resource(server).connect()
    return load_library(plex, section=section)


def load_library_by_baseurl(baseurl, token, section="Music") -> PlexLibrary:
    plex = PlexServer(baseurl, token)
    return load_library(plex, section=section)


def load_library(plex: PlexServer = None, section="Music") -> PlexLibrary:
    plex = plex if plex else PlexServer()
    return PlexLibrary(music=plex.library.section(section))
