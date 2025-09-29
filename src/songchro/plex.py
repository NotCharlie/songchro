import base64
import codecs
import json
import os.path
import re
import unicodedata
from collections.abc import Iterable, Iterator, Generator
from functools import cached_property
from pathlib import Path
from typing import Any, Protocol

import structlog
from multimethod import multimethod
from plexapi import playlist, audio
from plexapi.exceptions import NotFound, PlexApiException
from plexapi.library import MusicSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from songchro import model
from songchro.model import HasJsonDataEncoder

log = structlog.get_logger()


FOLDER_METADATA_HEADER = "### Songchro Folder metadata below, do NOT modify ###\n"
SMART_METADATA_HEADER = "### Songchro Smart metadata below, do NOT modify ###\n"
LIBRARY_TYPE = "plex"


class HasPlexPlaylist(Protocol):
    plex_playlist: playlist.Playlist


class AddsToPlexPlaylist:
    def add_item(self: HasPlexPlaylist, track: model.Track, after: model.Track) -> None:
        if isinstance(track, PlexTrack) and (isinstance(after, PlexTrack) or after is None):
            self.plex_playlist.addItems([track.plex_track])
            self.plex_playlist.reload()  # TODO: figure out why @cached_data_property on _items not forcing reload
            self.plex_playlist.moveItem(track.plex_track, after.plex_track if after else None)
        else:
            raise RuntimeError(f"incorrect track type: {type(track)} or {type(after)}")


class PlexTrack(model.Track):
    def __init__(self, plex_track: audio.Track, library: model.Library):
        super().__init__(
            name=plex_track.title,
            artist=plex_track.artist().title,
            album=plex_track.album().title,
            filepath=Path(os.path.relpath(plex_track.locations[0], start=library.music_root)),
            album_artist=plex_track.album().artist().title,
            disc_number=plex_track.parentIndex,
            track_number=plex_track.index,
            playcounts={LIBRARY_TYPE: plex_track.viewCount},
            library=library,
        )
        self.plex_track = plex_track

    def key(self):
        return self.plex_track.key

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        if isinstance(other, PlexTrack):
            return self.key() == other.key()
        return NotImplemented

    def increment_plays(self, increase):
        super().increment_plays(increase)
        for i in range(increase):
            self.plex_track.markPlayed()


class PlexPlaylist(AddsToPlexPlaylist, model.Playlist):
    def __init__(self, plex_playlist: playlist.Playlist, plex_lib: "PlexLibrary"):
        super().__init__(plex_playlist.title, plex_lib)
        self.plex_playlist = plex_playlist

    @cached_property
    def tracks(self) -> list[model.Track]:
        return [PlexTrack(track, self.library) for track in self.plex_playlist.items()]


class PlexPlaylistFolder(AddsToPlexPlaylist, model.TracksSyncer, model.PlaylistFolder):
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
        return [PlexTrack(track, self.library) for track in self.plex_playlist.items()]

    @multimethod
    def sync_tracks(self, other: model.Playlist, /, dry_run=False) -> bool:
        return super().sync_tracks(other, dry_run=dry_run)

    @multimethod
    def sync_tracks(self, other: model.PlaylistFolder, /, dry_run=False) -> bool:
        orig_tracks = self.tracks
        changed = super().sync_tracks(other, dry_run=dry_run)
        changed |= self.sync(orig_tracks, other.tracks, self.library.map_tracks, dry_run=dry_run)
        if not dry_run and changed:
            self.update_summary()
        return changed

    def update_summary(self):
        plex_playlist_summary = self.plex_playlist.summary
        if plex_playlist_summary:
            comment, _ = plex_playlist_summary.split(FOLDER_METADATA_HEADER, 1)
            comment += "\n"
        else:
            comment = ""
        summary = f"{comment}{FOLDER_METADATA_HEADER}{codecs.decode(base64.encodebytes(codecs.encode(json.dumps(self, cls=HasJsonDataEncoder))))}\n"
        self.plex_playlist.editSummary(summary)


class PlexSmartPlaylist(model.SmartPlaylist):
    def __init__(
        self,
        plex_playlist: playlist.Playlist,
        smart_criteria: dict[str, Any],
        plex_lib: "PlexLibrary",
    ):
        super().__init__(
            plex_playlist.title,
            smart_criteria,
            LIBRARY_TYPE,
            plex_lib,
        )
        self.plex_playlist = plex_playlist

    @property
    def tracks(self) -> Iterable[model.Track]:
        return (PlexTrack(track, self.library) for track in self.plex_playlist.items())

    def update_summary(self):
        plex_playlist_summary = self.plex_playlist.summary
        if plex_playlist_summary:
            comment, _ = plex_playlist_summary.split(SMART_METADATA_HEADER, 1)
            comment += "\n"
        else:
            comment = ""
        summary = f"{comment}{SMART_METADATA_HEADER}{codecs.decode(base64.encodebytes(codecs.encode(json.dumps(self, cls=HasJsonDataEncoder))))}\n"
        self.plex_playlist.editSummary(summary)


class PlexFilterSmartPlaylist(PlexSmartPlaylist):
    def __init__(
        self,
        plex_playlist: playlist.Playlist,
        plex_lib: "PlexLibrary",
    ):
        super().__init__(
            plex_playlist,
            {LIBRARY_TYPE: plex_playlist.filters()},
            plex_lib,
        )


class PlexExternalSmartPlaylist(PlexSmartPlaylist, AddsToPlexPlaylist, model.TracksSyncer):
    def __init__(
        self,
        plex_playlist: playlist.Playlist,
        smart_criteria: dict[str, Any],
        plex_lib: "PlexLibrary",
    ):
        super().__init__(plex_playlist, smart_criteria, plex_lib)

    def sync_tracks(self, other: model.NamedPlaylist, /, dry_run=False) -> bool:
        return self.sync(self.tracks, other.tracks, self.library.map_tracks, dry_run=dry_run)


class PlexLibrary(model.Library):
    def __init__(self, music_root: Path, music: MusicSection):
        super().__init__("Plex", LIBRARY_TYPE, music_root)
        self.music = music

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.music.getWebURL()}"

    @cached_property
    def tracks(self) -> list[model.Track]:
        return [PlexTrack(track, self) for track in self.music.searchTracks()]

    @cached_property
    def playlists(self) -> list[model.NamedPlaylist]:
        result: dict[str, model.NamedPlaylist] = {}
        folders: list[PlexPlaylistFolder] = []
        for pl in self.music.playlists():
            summary = pl.summary.replace("\r\n", "\n")
            if pl.smart:
                result[pl.title] = PlexFilterSmartPlaylist(pl, self)
            elif SMART_METADATA_HEADER in summary:
                # Decode the base64-encoded metadata following the header.
                _, b64_data = summary.split(SMART_METADATA_HEADER, 1)
                decoded_bytes = base64.decodebytes(codecs.encode(b64_data))
                # The decoded bytes represent the JSON of a smart criteria
                smart_json = json.loads(decoded_bytes)
                result[pl.title] = PlexExternalSmartPlaylist(pl, smart_json["smart_criteria"], self)
            elif FOLDER_METADATA_HEADER in summary:
                # Decode the base64-encoded metadata following the header.
                _, b64_data = summary.split(FOLDER_METADATA_HEADER, 1)
                decoded_bytes = base64.decodebytes(codecs.encode(b64_data))
                # The decoded bytes represent the JSON of a playlist folder
                folder_json = json.loads(decoded_bytes)
                named_subs = [model.NamedPlaylist(name, self) for name in folder_json["sub_playlists"]]
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
            " & ": " And ",
            " And ": " and ",
            " and ": " + ",
            " + ": " & ",
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
        return {"and": [{"or": [{key: element} for element in values if element]} for key, values in elements.items()]}

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
                        lambda track: track.album().artist().title == to_find.album_artist,
                    ),
                ]
                for fields, fn in combos:
                    log.debug("performing query", fields=fields)
                    query = self._make_filter({key: subqueries[key] for key in fields})
                    log.debug("query", query=query)
                    tracks = []

                    def normalized_endswith(src, to_find) -> bool:
                        norm_src = unicodedata.normalize("NFC", src)
                        norm_to_find = unicodedata.normalize("NFC", to_find)
                        return norm_src.endswith(norm_to_find)

                    try:
                        tracks = [
                            track
                            for track in self.music.searchTracks(filters=query)
                            if (track.parentIndex == to_find.disc_number or not to_find.disc_number)
                            and (not to_find.filepath or normalized_endswith(track.locations[0], str(to_find.filepath)))
                        ]
                        log.debug("resulting tracks", tracks=tracks)
                    except PlexApiException as e:
                        log.warning("exception during search()", fields=fields, e=e)
                    if fn:
                        tracks = list(filter(fn, tracks))
                    if tracks:
                        if len(tracks) == 1:
                            log.debug("track found", tracks=tracks)
                            return tracks
                        if tightest_match:
                            if len(tracks) < len(tightest_match):
                                log.debug(f"new tightest match", tracks=tracks, query=query)
                                tightest_match = tracks
                        else:
                            log.debug(f"initial tightest match", tracks=tracks, query=query)
                            tightest_match = tracks
        return tightest_match

    def find_track(self, to_find: model.Track) -> list[model.Track]:
        return [PlexTrack(track, self) for track in self._find_tightest_match(to_find)]

    def map_tracks(self, tracks: Iterable[model.Track], /, dry_run: bool = False) -> Iterator[model.Track]:
        errors = []
        size = 0
        for track in tracks:
            plex_track = self.find_track(track)
            if len(plex_track) != 1:
                msg = f"Found {len(plex_track)} tracks for {track}"
                if dry_run:
                    errors.append(msg)
                else:
                    raise model.NoSuchTrack(msg)
            else:
                size += 1
                yield plex_track[0]
        log.info(f"done with map_tracks", errors=errors, size=size)
        if errors:
            for index, error in enumerate(errors):
                log.error(f"  {index+1}. {error}")
            raise model.CollectedErrors("missing tracks", errors)

    def create_playlist(
        self,
        playlist_name: str,
        source: model.NamedPlaylist,
        dry_run=False,
        make_playlist_limit=1500,
    ) -> None:
        if not dry_run:
            try:
                self.music.playlist(playlist_name)
                log.critical("existing playlist", playlist_name=playlist_name)
                raise RuntimeError(f"existing playlist {playlist_name}")
            except NotFound:
                pass  # expected case
        new_playlist = None
        source_tracks = list(source.tracks)
        if len(source_tracks) < make_playlist_limit:
            plex_tracks = self.map_tracks(source.tracks, dry_run=dry_run)
            if not dry_run:
                new_playlist = self._make_playlist(source, playlist_name, plex_tracks)
        else:
            log.info("creating empty playlist & syncing", size=len(source_tracks))
            if not dry_run:
                first_track = self.map_tracks(source_tracks[:1], dry_run=dry_run)
                new_playlist = self._make_playlist(source, playlist_name, first_track)
                new_playlist.sync_tracks(source)
        if "playlists" in self.__dict__ and new_playlist:
            self.playlists.append(new_playlist)

    @multimethod
    def _make_playlist(self, _: model.Playlist, name: str, tracks: Generator) -> PlexPlaylist:
        return self.music.createPlaylist(name, [tr.plex_track for tr in tracks])

    @multimethod
    def _make_playlist(
        self,
        source: model.PlaylistFolder,
        name: str,
        tracks: Generator,
    ) -> PlexPlaylistFolder:
        new_playlist = self.music.createPlaylist(name, [tr.plex_track for tr in tracks])
        subs = [self.find_playlist(p.name) for p in source.sub_playlists]
        result = PlexPlaylistFolder(new_playlist, subs, self)
        result.update_summary()
        return result

    @multimethod
    def _make_playlist(
        self,
        source: model.SmartPlaylist,
        name: str,
        tracks: Generator,
    ) -> PlexSmartPlaylist:
        if plex_filters := source.smart_criteria.get(LIBRARY_TYPE):
            new_playlist = self.music.createPlaylist(name, smart=True, **plex_filters)
            result = PlexFilterSmartPlaylist(new_playlist, self)
        else:
            new_playlist = self.music.createPlaylist(name, [tr.plex_track for tr in tracks])
            result = PlexExternalSmartPlaylist(new_playlist, source.smart_criteria, self)
        result.update_summary()
        return result


def load_library_by_username(username, password, code, server, music_root, section="Music") -> PlexLibrary:
    account = MyPlexAccount(username, password, code=code)
    plex = account.resource(server).connect()
    return load_library(music_root, plex=plex, section=section)


def load_library_by_baseurl(baseurl, token, music_root, section="Music") -> PlexLibrary:
    plex = PlexServer(baseurl, token)
    return load_library(music_root, plex=plex, section=section)


def load_library(music_root, plex: PlexServer = None, section="Music") -> PlexLibrary:
    plex = plex if plex else PlexServer()
    return PlexLibrary(music_root=Path(music_root), music=plex.library.section(section))
