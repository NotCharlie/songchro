import glob
import json
import os
from collections.abc import Iterable
from pathlib import Path

import structlog

from songchro.model import (
    Playlist,
    Track,
    PlaylistFolder,
    SmartPlaylist,
    Library,
    NamedPlaylist,
)

log = structlog.get_logger()


class FilePlaylist(Playlist):
    def __init__(self, name: str, filename: Path, library: "FileLibrary", /, tracks):
        super().__init__(name, library, tracks=tracks)
        self.filename = filename

    def sync_tracks(self, other: Playlist, /, dry_run=False):
        changed = super().sync_tracks(other, dry_run=dry_run)
        if changed:
            log.info(
                "syncing updated playlist to file",
                filename=self.filename,
                tracks=self.tracks,
            )
            if not dry_run:
                with open(self.filename, "w", encoding="utf-8") as f:
                    f.write(self.to_json())
                    f.write("\n")


class FileLibrary(Library):
    def __init__(self, playlist_root: str, music_root: str):
        playlists = {}
        tracks = set()
        playlist_folders: list[PlaylistFolder] = []
        for filename in glob.glob(f"{playlist_root}/*.json"):
            with open(filename, "r") as f:
                to_import = json.load(f)
                if "sub_playlists" in to_import:
                    new_playlist = PlaylistFolder(
                        to_import["name"],
                        [
                            NamedPlaylist(name, self)
                            for name in to_import["sub_playlists"]
                        ],
                        self,
                    )
                    playlist_folders.append(new_playlist)
                elif "smart_criteria" in to_import:
                    new_playlist = SmartPlaylist(
                        to_import["name"], to_import["smart_criteria"], self
                    )
                else:
                    pl_tracks = [
                        Track(**track) for track in to_import.get("tracks", [])
                    ]
                    tracks.update(pl_tracks)
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
            Path(music_root),
            tracks=list(tracks),
            playlists=list(playlists.values()),
        )
        self.playlist_root = playlist_root

    def map_tracks(
        self, tracks: Iterable[Track], /, dry_run: bool = False
    ) -> list[Track]:
        return [Track(**track.json_data()) for track in tracks]

    def create_playlist(
        self, playlist_name: str, tracks: Iterable[Track], dry_run=False
    ) -> None:
        new_tracks = self.map_tracks(tracks, dry_run=dry_run)
        filename = os.path.join(self.playlist_root, f"{playlist_name}.json")
        new_playlist = FilePlaylist(
            playlist_name, Path(filename), self, tracks=new_tracks
        )
        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_playlist.to_json())
            f.write("\n")


def load_library(playlist_root: str, music_root: str) -> FileLibrary:
    return FileLibrary(playlist_root, music_root)
