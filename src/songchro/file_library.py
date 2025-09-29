import glob
import json
import os
import unicodedata
from collections.abc import Iterable, Callable, Iterator, Generator
from pathlib import Path
from typing import Protocol, Any

import structlog
from multimethod import multimethod
from simpleeval import SimpleEval, InvalidExpression

from songchro import music_metadata
from songchro.model import (
    Playlist,
    Track,
    PlaylistFolder,
    SmartPlaylist,
    Library,
    NamedPlaylist,
    HasJsonDataEncoder,
    SongchroException,
    NoSuchTrack,
)
from songchro.music_metadata import MetadataError

log = structlog.get_logger()


LIBRARY_TYPE: str = "file"


class InvalidTrack(SongchroException):
    pass


class HasFilename(Protocol):
    filename: str


class FilePlaylistPersistence:
    def write_file(self: HasFilename):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self, f, cls=HasJsonDataEncoder, indent=2)
            f.write("\n")


class FileTrack(Track):
    def __init__(
        self,
        name=None,
        artist=None,
        album=None,
        album_artist=None,
        disc_number=None,
        track_number=None,
        filepath=None,
        playcounts=None,
        metadata=None,
        library=None,
    ):
        super().__init__(
            name=name,
            artist=artist,
            album=album,
            album_artist=album_artist,
            disc_number=disc_number,
            track_number=track_number,
            filepath=filepath,
            playcounts=playcounts if playcounts else {},
            library=library,
        )
        self.metadata = metadata

    @classmethod
    def from_file(
        cls, fpath: Path, library: Library, /, music_root: str | None = None
    ) -> "FileTrack":
        metadata = music_metadata.for_file(fpath, music_root)
        return FileTrack(
            name=metadata.title,
            artist=metadata.artist,
            album=metadata.album_title,
            album_artist=metadata.album_artist,
            disc_number=metadata.disc_number,
            track_number=metadata.track_number,
            filepath=os.path.relpath(
                fpath, start=music_root if music_root else library.music_root
            ),
            playcounts={},
            metadata=metadata,
            library=library,
        )

    @classmethod
    def from_dict(
        cls, json_dct: dict, library: Library, /, music_root: str | None = None
    ) -> "FileTrack":
        return FileTrack(**json_dct, library=library)

    def json_data(self) -> dict[str, Any]:
        result = super().json_data()
        result["metadata"] = self.metadata
        return result


class FilePlaylist(Playlist, FilePlaylistPersistence):
    def __init__(self, name: str, filename: Path, library: "FileLibrary", /, tracks):
        super().__init__(name, library, tracks=tracks)
        self.filename = filename

    def sync_tracks(self, other: NamedPlaylist, /, dry_run=False) -> bool:
        changed = super().sync_tracks(other, dry_run=dry_run)
        if changed:
            log.info(
                "syncing updated playlist to file",
                filename=self.filename,
                tracks=self.tracks,
            )
            if not dry_run:
                self.write_file()
        return changed

    def json_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [track.filepath for track in self.tracks],
        }


class FilePlaylistFolder(PlaylistFolder, FilePlaylistPersistence):
    def __init__(
        self,
        name: str,
        subs: list[NamedPlaylist],
        filename: Path,
        library: "FileLibrary",
    ):
        super().__init__(name, subs, library)
        self.filename = filename

    def sync_tracks(self, other: NamedPlaylist, /, dry_run=False) -> bool:
        changed = super().sync_tracks(other, dry_run=dry_run)
        log.debug("sync_tracks", changed=changed)
        if changed:
            log.info(
                "syncing updated playlist to file",
                filename=self.filename,
                sub_playlists=self.sub_playlists,
            )
            if not dry_run:
                self.write_file()
        return changed


class FileSmartPlaylist(SmartPlaylist, FilePlaylistPersistence):
    def __init__(
        self,
        name: str,
        smart_criteria: dict[str, Any],
        filename: Path,
        library: "FileLibrary",
    ):
        super().__init__(name, smart_criteria, "file", library)
        self.se = SimpleEval()
        self.filename = filename

    def _filter(self) -> Callable[[Track], bool]:
        parsed = self.se.parse(self.smart_criteria[self.criteria_key]["filter"])

        def fn(track: Track) -> bool:
            self.se.names = track.metadata
            try:
                return self.se.eval(
                    f'preparsed: {self.smart_criteria[self.criteria_key]["filter"]}',
                    parsed,
                )
            except InvalidExpression as e:
                log.warning(
                    "failed to evaluate filter",
                    e=e,
                    track=track,
                    metadata=track.metadata,
                )
            return False

        return fn


class FileExternalSmartPlaylist(FileSmartPlaylist):
    @property
    def tracks(self) -> Iterable[Track]:
        return []


class FileLibrary(Library):
    def __init__(self, tracks_file: str, playlist_root: str, music_root: str):
        self.tracks_file = tracks_file
        playlists = {}
        playlist_folders: list[PlaylistFolder] = []

        # Build a mapping of music file paths to FileTrack objects.
        self.track_for_path: dict[str, FileTrack] = {}

        def decode_track(dct) -> FileTrack | dict:
            if "filepath" in dct:
                return FileTrack.from_dict(dct, self, music_root)
            return dct

        if os.path.exists(tracks_file):
            with open(tracks_file, "r") as f:
                self.track_for_path = json.load(f, object_hook=decode_track)
        else:
            self.track_for_path = {}

        for filename in glob.glob(f"{playlist_root}/*.json"):
            with open(filename, "r") as f:
                to_import = json.load(f)
                if "sub_playlists" in to_import:
                    new_playlist = FilePlaylistFolder(
                        to_import["name"],
                        [
                            NamedPlaylist(name, self)
                            for name in to_import["sub_playlists"]
                        ],
                        Path(filename),
                        self,
                    )
                    playlist_folders.append(new_playlist)
                elif criteria := to_import.get("smart_criteria", {}):
                    if criteria.get(LIBRARY_TYPE):
                        new_playlist = FileSmartPlaylist(
                            to_import["name"],
                            criteria,
                            Path(filename),
                            self,
                        )
                    else:
                        new_playlist = FileExternalSmartPlaylist(
                            to_import["name"],
                            criteria,
                            Path(filename),
                            self,
                        )
                else:
                    pl_tracks = []
                    for track in to_import.get("tracks", []):
                        if isinstance(track, str):
                            filepath = track
                        elif isinstance(track, dict):
                            filepath = track["filepath"]
                        else:
                            raise InvalidTrack(track)
                        pl_tracks.append(self._find_track_for_path(filepath))
                    new_playlist = FilePlaylist(
                        to_import["name"], Path(filename), self, tracks=pl_tracks
                    )
                playlists[to_import["name"]] = new_playlist
        for playlist_folder in playlist_folders:
            playlist_folder.sub_playlists = [
                playlists[playlist.name] for playlist in playlist_folder.sub_playlists
            ]
        super().__init__(
            "File",
            LIBRARY_TYPE,
            Path(music_root),
            tracks=list(self.track_for_path.values()),
            playlists=list(playlists.values()),
        )
        self.playlist_root = playlist_root

    def _find_track_for_path(self, fpath: str) -> FileTrack:
        return self.track_for_path.get(unicodedata.normalize("NFC", fpath))

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.tracks_file}"

    def find_track(self, track: Track) -> list[Track]:
        return [self._find_track_for_path(track.filepath)]

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

    def create_playlist(
        self,
        playlist_name: str,
        source: NamedPlaylist,
        dry_run=False,
    ) -> None:
        new_tracks = self.map_tracks(source.tracks, dry_run=dry_run)
        filename = os.path.join(self.playlist_root, f"{playlist_name}.json")
        new_playlist = self._make_playlist(source, playlist_name, new_tracks, filename)
        if not dry_run:
            new_playlist.write_file()
        else:
            log.info(
                f"DRY-RUN: not writing to file",
                playlist=new_playlist,
                filename=filename,
            )

    @multimethod
    def _make_playlist(
        self, _: Playlist, name: str, tracks: Generator, filename: str
    ) -> FilePlaylist:
        return FilePlaylist(name, Path(filename), self, tracks=list(tracks))

    @multimethod
    def _make_playlist(
        self, source: PlaylistFolder, name: str, tracks: Generator, filename: str
    ) -> FilePlaylistFolder:
        subs = [self.find_playlist(p.name) for p in source.sub_playlists]
        return FilePlaylistFolder(name, subs, Path(filename), self)

    @multimethod
    def _make_playlist(
        self, source: SmartPlaylist, name: str, tracks: Generator, filename: str
    ) -> FileSmartPlaylist:
        if LIBRARY_TYPE in source.smart_criteria:
            return FileSmartPlaylist(
                name,
                source.smart_criteria,
                Path(os.path.join(self.playlist_root, f"{name}.json")),
                self,
            )
        else:
            return FileExternalSmartPlaylist(
                name,
                source.smart_criteria,
                Path(os.path.join(self.playlist_root, f"{name}.json")),
                self,
            )

    def update_metadata(self, subdir=""):
        for fpath in mp3_m4a_files(os.path.join(self.music_root, subdir)):
            relpath = unicodedata.normalize(
                "NFC", os.path.relpath(fpath, start=self.music_root)
            )
            log.debug("read file", fpath=fpath)
            try:
                new_meta = FileTrack.from_file(
                    fpath, self, music_root=str(self.music_root)
                )
                if existing_track := self.track_for_path.get(relpath):
                    new_meta.playcounts = existing_track.playcounts.copy()
                self.track_for_path[relpath] = new_meta
            except MetadataError as e:
                log.warning("error on metadata update", fpath=fpath, error=e)
        self.save_tracks()

    def save_tracks(self):
        with open(self.tracks_file, "w", encoding="utf-8") as f:
            json.dump(
                self.track_for_path, f, cls=HasJsonDataEncoder, indent=2, sort_keys=True
            )

    @multimethod
    def migrate_playlist(self, playlist: FilePlaylist):
        playlist.write_file()

    @multimethod
    def migrate_playlist(self, playlist: NamedPlaylist):
        log.warning("no migration needed", type=playlist.__class__.__name__)


def mp3_m4a_files(root_dir: str | os.PathLike) -> Iterator[Path]:
    """
    Yield all files under *root_dir* (recursively) that have a .mp3 or .m4a extension.

    Parameters
    ----------
    root_dir : str | PathLike
        The directory to search.  Can be a string, pathlib.Path, etc.

    Yields
    ------
    pathlib.Path
        Full path objects pointing at the matching files.
    """
    # Ensure we’re working with a pathlib.Path object for convenience
    root = Path(root_dir)

    if not root.is_dir():
        raise ValueError(f"{root!s} is not a directory")

    # Iterate over all files in the tree
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(("#", "@eaDir"))]
        for name in filenames:
            # Quick string‑based check – faster than calling Path.suffix each time
            if name.lower().endswith((".mp3", ".m4a")):
                yield Path(dirpath) / name


def load_library(tracks_file: str, playlist_root: str, music_root: str) -> FileLibrary:
    return FileLibrary(tracks_file, playlist_root, music_root)
