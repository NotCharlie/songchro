from collections import defaultdict
from typing import Type

import click
import structlog

from songchro import model, file_library

log = structlog.get_logger()


def list_playlists(
    library: model.Library, songs: bool, simple: bool, kind: Type[model.NamedPlaylist]
) -> None:
    if not simple:
        click.echo(f"Listing {library.source} playlists:")
    for playlist in (
        p
        for p in sorted(library.playlists, key=lambda pl: pl.name)
        if isinstance(p, kind)
    ):
        if simple:
            click.echo(playlist.name)
        else:
            click.echo(f"  * {playlist.name}")
            if songs:
                for track in playlist.tracks:
                    click.echo(f"    - {track.name} / {track.artist} / {track.album}")


def export_playlist(
    source: model.Library, name: str, target: model.Library, dry_run: bool
) -> None:
    click.echo(f"Exporting {source.source} playlist: {name}")
    playlist = source.find_playlist(name)
    if playlist:
        click.echo(f"Found {source.source} playlist: {name}")
        target.create_playlist(name, playlist, dry_run=dry_run)
    else:
        click.echo(f"No {source.source} playlist: {name}")


def export_all_playlists(
    source: model.Library, target: model.Library, dry_run: bool
) -> None:
    click.echo(f"Exporting all {source.source} playlists to {target.source}")
    for playlist in (
        p for p in source.playlists if not isinstance(p, model.SmartPlaylist)
    ):
        target.create_playlist(playlist.name, playlist, dry_run)


def import_playlist(
    source: model.Library, name: str, target: model.Library, /, dry_run=False
) -> None:
    click.echo(f"Importing playlist to {target.source} from {source.source} {name}")
    playlist = source.find_playlist(name)
    if playlist:
        click.echo(f"Found {source.source} playlist: {name}")
        target.create_playlist(name, playlist, dry_run=dry_run)
        if not dry_run:
            new_playlist = target.find_playlist(name)
            click.echo(f"Created new {target.source} playlist: {new_playlist.name}")
        else:
            click.echo(f"DRY-RUN: skip creating {target.source} playlist {name}")
    else:
        click.echo(f"No {source.source} playlist: {name}")


def sync_plays(
    dest: file_library.FileLibrary,
    srcs: dict[str, model.Library],
    /,
    dry_run=False,
    skip_increase=False,
):
    all_keys = set(key for key in srcs.keys())
    updates = {}
    for track in dest.tracks:
        lib_track: dict[str, model.Track] = {}
        increase_for = defaultdict(int)
        for libname in all_keys:
            lib_tracks = srcs[libname].find_track(track)
            if lib_tracks:
                lib_track[libname] = lib_tracks[0]
                lib_count = lib_tracks[0].playcounts.get(libname, 0)
                dest_count = track.playcounts.get(libname, 0)
                delta = max(lib_count - dest_count, 0)
                for others in all_keys - {libname}:
                    increase_for[others] += delta
            else:
                log.debug(
                    "no matching track for playcount", libname=libname, track=track
                )
        if sum(increase_for.values()):
            updates[track] = (lib_track, increase_for)
        else:
            log.debug("no increases to playcount", track=track)

    for track, (lib_track, increase_for) in updates.items():
        log.info("increments for track", track=track, increase_for=increase_for)
        for libname in all_keys:
            if libname in lib_track:
                if not dry_run:
                    if (increase := increase_for.get(libname)) and not skip_increase:
                        lib_track[libname].increment_plays(increase)
                    track.playcounts[libname] = lib_track[libname].playcounts[libname]
                else:
                    log.debug(
                        "DRY-RUN: skipping play count updates",
                        track=track,
                        increase_for=increase_for,
                    )
            else:
                log.warning(
                    "no matching track for `increment_plays`",
                    libname=libname,
                    track=track,
                )
        log.info("resulting play counts", track=track)

    if not dry_run:
        dest.save_tracks()
    else:
        click.echo("skipping updates to track file")
