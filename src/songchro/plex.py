import base64
import codecs
import json
import os.path
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Protocol

import structlog
from multimethod import multimethod
from plexapi import playlist, audio
from plexapi.exceptions import NotFound
from plexapi.library import MusicSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from songchro import model

log = structlog.get_logger()


FOLDER_METADATA_HEADER = "### Songchro Folder metadata below, do NOT modify ###\n"


class HasPlexPlaylist(Protocol):
    plex_playlist: playlist.Playlist


class AddsToPlexPlaylist:
    def add_item(self: HasPlexPlaylist, track: model.Track, after: model.Track) -> None:
        if isinstance(track, PlexTrack) and (
            isinstance(after, PlexTrack) or after is None
        ):
            self.plex_playlist.addItems([track.plex_track])
            self.plex_playlist.reload()  # TODO: figure out why @cached_data_property on _items not forcing reload
            self.plex_playlist.moveItem(
                track.plex_track, after.plex_track if after else None
            )
        else:
            raise RuntimeError(f"incorrect track type: {type(track)} or {type(after)}")


@dataclass
class PlexTrack(model.Track):
    plex_track: audio.Track

    def key(self):
        return self.plex_track.key

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, PlexTrack):
            return self.key() == other.key()
        return NotImplemented


class PlexPlaylist(model.Playlist, AddsToPlexPlaylist):
    def __init__(self, plex_playlist: playlist.Playlist, plex_lib: "PlexLibrary"):
        super().__init__(plex_playlist.title, plex_lib)
        self.plex_playlist = plex_playlist

    @cached_property
    def tracks(self) -> list[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(
                    os.path.relpath(track.locations[0], start=self.library.music_root)
                ),
                album_artist=track.album().artist().title,
                disc_number=track.parentIndex,
                track_number=track.index,
            )
            for track in self.plex_playlist.items()
        ]


class PlexPlaylistFolder(model.PlaylistFolder, AddsToPlexPlaylist, model.TracksSyncer):
    def __init__(
        self,
        plex_playlist: playlist.Playlist,
        sub_playlists: list[model.NamedPlaylist],
        library: "PlexLibrary",
    ):
        super().__init__(plex_playlist.title, sub_playlists, library)
        self.plex_playlist = plex_playlist

    @property
    def tracks(self) -> Iterable[model.Track]:
        deduped = {track: None for track in super().tracks}
        return deduped.keys()

    @multimethod
    def sync_tracks(self, other: model.Playlist, /, dry_run=False) -> bool:
        return super().sync_tracks(other, dry_run=dry_run)

    @multimethod
    def sync_tracks(self, other: model.PlaylistFolder, /, dry_run=False) -> bool:
        orig_tracks = self.tracks
        changed = super().sync_tracks(other, dry_run=dry_run)
        if changed or orig_tracks != self.tracks:
            changed |= self.sync(
                orig_tracks, other.tracks, self.library.map_tracks, dry_run=dry_run
            )
        if changed:
            self.update_summary()
        return changed

    def update_summary(self):
        summary = f"{FOLDER_METADATA_HEADER}{codecs.decode(base64.encodebytes(codecs.encode(self.to_json())))}\n"
        self.plex_playlist.editSummary(summary)


class PlexSmartPlaylist(model.SmartPlaylist):
    def __init__(self, plex_playlist: playlist.Playlist, plex_lib: "PlexLibrary"):
        super().__init__(plex_playlist.title, "TODO", plex_lib)
        self.plex_playlist = plex_playlist
        self.plex_filters = plex_playlist.filters()

    def json_data(self) -> dict[str, Any]:
        data = super().json_data()
        data["filters"] = self.plex_filters
        return data


class PlexLibrary(model.Library):
    def __init__(self, music_root: Path, music: MusicSection):
        super().__init__("Plex", music_root)
        self.music = music

    @cached_property
    def tracks(self) -> list[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(
                    os.path.relpath(track.locations[0], start=self.music_root)
                ),
                album_artist=track.album().artist().title,
            )
            for track in self.music.searchTracks()
        ]

    @cached_property
    def playlists(self) -> list[model.NamedPlaylist]:
        result: dict[str, model.NamedPlaylist] = {}
        folders: list[PlexPlaylistFolder] = []
        for pl in self.music.playlists():
            summary = pl.summary.replace("\r\n", "\n")
            if pl.smart:
                result[pl.title] = PlexSmartPlaylist(pl, self)
            elif FOLDER_METADATA_HEADER in summary:
                # Decode the base64-encoded metadata following the header.
                _, b64_data = summary.split(FOLDER_METADATA_HEADER, 1)
                decoded_bytes = base64.decodebytes(codecs.encode(b64_data))
                # The decoded bytes represent the JSON of a playlist folder;
                folder_json = json.loads(decoded_bytes)
                named_subs = [
                    model.NamedPlaylist(name, self)
                    for name in folder_json["sub_playlists"]
                ]
                new_playlist = PlexPlaylistFolder(pl, named_subs, self)
                folders.append(new_playlist)
                result[pl.title] = new_playlist
            else:
                result[pl.title] = PlexPlaylist(pl, self)
        for folder in folders:
            folder.sub_playlists = [result[sub.name] for sub in folder.sub_playlists]
        return list(result.values())

    @staticmethod
    def _perform_replacements(data: str) -> set[str]:
        if not data:
            return set()
        result = {data}
        processed = set()
        queue = [data]

        subs = {
            "-": "\u2010",
            "\u2010": "\u2013",
            "''": '"',
            "'": "\u2019",
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
            "...": "\u2026",
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
    def _strip_regexes(data: str):
        if not data:
            yield ""
            return
        processed = set()
        queue = [data]
        regexes = [
            (re.compile(r"\((.*?)\)$"), r"\g<1>"),
            (re.compile(r"\[(.*?)]$"), r"(\g<1>)"),
            (re.compile(r'"(.*?)"'), r"\\u201c\g<1>\\u201d"),
            (re.compile(r" \(.*?\)$"), ""),
            (re.compile(r" \[.*?]$"), ""),
            (re.compile(r" - .*?$"), ""),
            (re.compile(r" EP$"), ""),
            (re.compile(r" Soundtrack$"), ""),
            (re.compile(r" OST$"), ""),
            (re.compile(r"^.*?: "), ""),
            (re.compile(r"^\(.*?\) "), ""),
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
    def _make_filter(elements: dict[str, Iterable[str]]) -> dict[str, Any]:
        return {
            "and": [
                {"or": [{key: element} for element in values if element]}
                for key, values in elements.items()
            ]
        }

    def _find_tightest_match(self, to_find: model.Track) -> list[audio.Track]:
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
                    log.debug("query", query=query)
                    tracks = []
                    try:
                        tracks = [
                            track
                            for track in self.music.searchTracks(filters=query)
                            if (
                                track.parentIndex == to_find.disc_number
                                or not to_find.disc_number
                            )
                            and (
                                track.locations[0].endswith(to_find.filepath)
                                or not to_find.filepath
                            )
                        ]
                        log.debug("resulting tracks", tracks=tracks)
                    except Exception as e:
                        log.warning("exception during search()", fields=fields, e=e)
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

    def find_track(self, to_find: model.Track) -> list[model.Track]:
        return [
            PlexTrack(
                plex_track=track,
                name=track.title,
                artist=track.artist().title,
                album=track.album().title,
                filepath=Path(
                    os.path.relpath(track.locations[0], start=self.music_root)
                ),
                album_artist=track.album().artist().title,
                track_number=track.trackNumber,
                disc_number=track.parentIndex,
            )
            for track in self._find_tightest_match(to_find)
        ]

    def map_tracks(
        self, tracks: Iterable[model.Track], /, dry_run: bool = False
    ) -> list[PlexTrack]:
        errors = []
        result = {}
        for track in tracks:
            plex_track = self.find_track(track)
            if len(plex_track) != 1:
                msg = f"Found {len(plex_track)} tracks for {track}"
                if dry_run:
                    errors.append(msg)
                else:
                    raise RuntimeError(msg)
            else:
                result[plex_track[0]] = None
        log.info(f"done with map_tracks", errors=errors, size=len(result))
        if errors:
            for index, error in enumerate(errors):
                log.error(f"  {index+1}. {error}")
            raise RuntimeError(f"Found {len(errors)} errors")
        return list(result.keys())

    def create_playlist(
        self,
        playlist_name: str,
        source: model.NamedPlaylist,
        dry_run=False,
    ) -> None:
        if not dry_run:
            try:
                self.music.playlist(playlist_name)
                log.critical("existing playlist", playlist_name=playlist_name)
                raise RuntimeError(f"existing playlist {playlist_name}")
            except NotFound:
                pass  # expected case
        plex_tracks = self.map_tracks(source.tracks, dry_run=dry_run)
        if not dry_run:
            new_playlist = self._make_playlist(source, playlist_name, plex_tracks)
            if "playlists" in self.__dict__:
                self.playlists.append(new_playlist)

    @multimethod
    def _make_playlist(
        self, _: model.Playlist, name: str, tracks: list[PlexTrack]
    ) -> PlexPlaylist:
        return self.music.createPlaylist(name, [tr.plex_track for tr in tracks])

    @multimethod
    def _make_playlist(
        self,
        source: model.PlaylistFolder,
        name: str,
        tracks: list[PlexTrack],
    ) -> PlexPlaylistFolder:
        new_playlist = self.music.createPlaylist(name, [tr.plex_track for tr in tracks])
        subs = [self.find_playlist(p.name) for p in source.sub_playlists]
        result = PlexPlaylistFolder(new_playlist, subs, self)
        result.update_summary()
        return result


def load_library_by_username(
    username, password, code, server, music_root, section="Music"
) -> PlexLibrary:
    account = MyPlexAccount(username, password, code=code)
    plex = account.resource(server).connect()
    return load_library(music_root, plex=plex, section=section)


def load_library_by_baseurl(baseurl, token, music_root, section="Music") -> PlexLibrary:
    plex = PlexServer(baseurl, token)
    return load_library(music_root, plex=plex, section=section)


def load_library(music_root, plex: PlexServer = None, section="Music") -> PlexLibrary:
    plex = plex if plex else PlexServer()
    return PlexLibrary(music_root=Path(music_root), music=plex.library.section(section))
