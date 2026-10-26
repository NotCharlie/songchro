#!/usr/bin/env python3
"""
CLI interface for songchro using Click.
"""
import json
import logging
import os
import sys
from pathlib import Path

import click
import structlog
import yaml

import songchro.file_library as fl
import songchro.itunes as it
import songchro.plex as pl
from songchro import __version__, apple_music, commands, model

CLASS_FOR_KIND = {
    "plain": model.Playlist,
    "folder": model.PlaylistFolder,
    "smart": model.SmartPlaylist,
    "all": model.NamedPlaylist,
}


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--logging-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Logging level",
)
@click.option(
    "--config",
    "config_file",
    type=click.Path(dir_okay=False),
    default=os.path.expanduser("~/.config/songchro/config.yml"),
    help="Configuration file.",
)
@click.pass_context
def cli(ctx, logging_level: str, config_file: str):
    """Synchronize playlists between iTunes and Plex."""
    ctx.ensure_object(dict)

    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            ctx.obj["config"] = config = yaml.safe_load(f) or {}
    else:
        ctx.obj["config"] = config = {}

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(logging_level or config.get("logging", "WARNING")),
        )
    )

    file_config = config.get("file", {})
    if file_config:
        ctx.obj["file_library"] = fl.load_library(file_config)


@cli.group()
@click.pass_context
def file(ctx):
    pass


@file.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show all songs.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
@click.option(
    "--kind",
    type=click.Choice(["plain", "folder", "smart", "all"]),
    default="plain",
    help="Kind of playlists to list.",
)
def file_list(
    ctx,
    songs: bool,
    simple: bool,
    kind: str,
):
    library = ctx.obj["file_library"]
    commands.list_playlists(library, songs, simple, CLASS_FOR_KIND[kind])


@file.command("update-meta")
@click.argument("subdir", required=False, default="", type=Path)
@click.pass_context
def file_update_meta(ctx, subdir):
    library: fl.FileLibrary = ctx.obj["file_library"]
    library.update_metadata(subdir=subdir)


@file.command("migrate")
@click.argument("playlist", required=True, type=str)
@click.pass_context
def file_migrate_playlist(ctx, playlist):
    library: fl.FileLibrary = ctx.obj["file_library"]
    library.migrate_playlist(library.find_playlist(playlist))


@cli.group()
@click.pass_context
def apple(ctx):
    apple_config = ctx.obj["config"].get(apple_music.LIBRARY_TYPE, {})
    ctx.obj["apple_music"] = apple_music.load_library(apple_config)


@apple.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
@click.option(
    "--kind",
    type=click.Choice(["plain", "folder", "smart", "all"]),
    default="plain",
    help="Kind of playlists to list.",
)
def apple_list(ctx, songs: bool, simple: bool, kind: str):
    library = ctx.obj["apple_music"]
    commands.list_playlists(
        library,
        songs,
        simple,
        CLASS_FOR_KIND[kind],
    )


@apple.command("export")
@click.argument("playlist_name")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def apple_export(ctx, playlist_name: str, dry_run: bool):
    """Export a playlist from local Apple Music to the local library."""
    file_library = ctx.obj["file_library"]
    library = ctx.obj["apple_music"]
    commands.export_playlist(library, playlist_name, file_library, dry_run=dry_run)


@cli.group()
@click.pass_context
def itunes(ctx):
    """Commands for working with iTunes playlists."""
    itunes_config = ctx.obj["config"].get(it.LIBRARY_TYPE, {})
    ctx.obj["itunes_library"] = it.load_library(itunes_config)


@itunes.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
@click.option(
    "--kind",
    type=click.Choice(["plain", "folder", "smart", "all"]),
    default="plain",
    help="Kind of playlists to list.",
)
def itunes_list(ctx, songs: bool, simple: bool, kind: str):
    """List available iTunes playlists."""
    library = ctx.obj["itunes_library"]
    commands.list_playlists(
        library,
        songs,
        simple,
        CLASS_FOR_KIND[kind],
    )


@itunes.command("export")
@click.argument("playlist_name")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def itunes_export(ctx, playlist_name: str, dry_run: bool):
    """Export an iTunes playlist to the local library."""
    file_library = ctx.obj["file_library"]
    library = ctx.obj["itunes_library"]
    commands.export_playlist(library, playlist_name, file_library, dry_run=dry_run)


@itunes.command("export_all")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def itunes_export_all(ctx, dry_run: bool):
    file_library = ctx.obj["file_library"]
    library = ctx.obj["itunes_library"]
    commands.export_all_playlists(library, file_library, dry_run)


@cli.group()
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.pass_context
def plex(
    ctx,
    code: str,
):
    """Commands for working with Plex playlists."""
    plex_config = ctx.obj["config"].get(pl.LIBRARY_TYPE, {})
    plex_config["code"] = code
    ctx.obj["plex_library"] = pl.load_library(plex_config)


@plex.command("list")
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
@click.option(
    "--kind",
    type=click.Choice(["plain", "folder", "smart", "all"]),
    default="plain",
    help="Kind of playlists to list.",
)
@click.pass_context
def plex_list(ctx, songs: bool, simple: bool, kind: str):
    """List available Plex playlists."""
    library = ctx.obj["plex_library"]
    commands.list_playlists(library, songs, simple, CLASS_FOR_KIND[kind])


@plex.command("export")
@click.argument("playlist_name")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def plex_export(ctx, playlist_name: str, dry_run: bool):
    """Export a Plex playlist to the local library."""
    file_library = ctx.obj["file_library"]
    library = ctx.obj["plex_library"]
    commands.export_playlist(library, playlist_name, file_library, dry_run)


@plex.command("export_all")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def plex_export_all(ctx, dry_run: bool):
    file_library = ctx.obj["file_library"]
    plex_library = ctx.obj["plex_library"]
    commands.export_all_playlists(plex_library, file_library, dry_run)


@plex.command("find")
@click.option("--song-file", "--s", type=click.Path(exists=True), help="Song file json.")
@click.option("--title", "-t", type=str, default="", help="Search title.")
@click.option("--artist", "-ar", type=str, default="", help="Search artist.")
@click.option("--album", "-al", type=str, default="", help="Search album.")
@click.option("--album-artist", "-aa", type=str, default="", help="Search album artist.")
@click.option("--filepath", "-f", type=str, default="", help="Search file path.")
@click.pass_context
def plex_find(
    ctx,
    song_file: str,
    title: str,
    artist: str,
    album: str,
    album_artist: str,
    filepath: str,
):
    """Find a Plex song."""
    library = ctx.obj["plex_library"]
    if song_file:
        click.echo(f"Finding song: {song_file}")
        with open(song_file) as f:
            track = model.Track(**json.load(f))
    else:
        track = model.Track(
            name=title,
            artist=artist,
            album=album,
            album_artist=album_artist,
            filepath=Path(library.standardize_path(filepath)),
        )
    plex_tracks = library.find_track(track)
    for plex_track in plex_tracks:
        click.echo(f"  * {track} -> {plex_track}")


@plex.command("import")
@click.argument("playlist", type=str)
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def plex_import(ctx, playlist: str, dry_run: bool):
    """Import a playlist to Plex."""
    library = ctx.obj["plex_library"]
    file_library = ctx.obj["file_library"]
    commands.import_playlist(file_library, playlist, library, dry_run=dry_run)


def _src_and_dst(ctx, source_type: str, destination_type: str) -> tuple[model.Library, model.Library]:
    libs: dict[str, model.Library] = {}
    if source_type == it.LIBRARY_TYPE or destination_type == it.LIBRARY_TYPE:
        itunes_config = ctx.obj["config"].get(it.LIBRARY_TYPE, {})
        libs[it.LIBRARY_TYPE] = it.load_library(itunes_config)
    if source_type == pl.LIBRARY_TYPE or destination_type == pl.LIBRARY_TYPE:
        plex_config = ctx.obj["config"].get(pl.LIBRARY_TYPE, {})
        plex_config["code"] = ctx.obj["code"]
        libs[pl.LIBRARY_TYPE] = pl.load_library(plex_config)
    if source_type == fl.LIBRARY_TYPE or destination_type == fl.LIBRARY_TYPE:
        libs[fl.LIBRARY_TYPE] = ctx.obj["file_library"]
    if source_type == apple_music.LIBRARY_TYPE or destination_type == apple_music.LIBRARY_TYPE:
        apple_music_config = ctx.obj["config"].get(apple_music.LIBRARY_TYPE, {})
        libs[apple_music.LIBRARY_TYPE] = apple_music.load_library(apple_music_config)

    return libs[source_type], libs[destination_type]


@cli.command()
@click.argument("playlist")
@click.option(
    "--source-type",
    "--from",
    type=click.Choice([it.LIBRARY_TYPE, pl.LIBRARY_TYPE, fl.LIBRARY_TYPE, apple_music.LIBRARY_TYPE]),
    default=fl.LIBRARY_TYPE,
    help=f"Source playlist type (default: {fl.LIBRARY_TYPE})",
)
@click.option(
    "--destination-type",
    "--to",
    type=click.Choice([it.LIBRARY_TYPE, pl.LIBRARY_TYPE, fl.LIBRARY_TYPE, apple_music.LIBRARY_TYPE]),
    default=pl.LIBRARY_TYPE,
    help=f"Destination playlist type (default: {pl.LIBRARY_TYPE})",
)
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def sync(
    ctx,
    playlist: str,
    source_type: str,
    destination_type: str,
    code: str,
    dry_run: bool,
):
    """Synchronize playlists between platforms."""

    click.echo(f"Syncing from {source_type} to {destination_type} for playlist '{playlist}' ")
    ctx.obj["code"] = code
    src_lib, dest_lib = _src_and_dst(ctx, source_type, destination_type)
    src = src_lib.find_playlist(playlist)
    dest = dest_lib.find_playlist(playlist)

    click.echo(f"Syncing from {src} to {dest}...")
    dest.sync_tracks(src, dry_run=dry_run)


@cli.command()
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.option("--skip-increase", is_flag=True, help="Skip calling `increase_plays`")
@click.pass_context
def sync_plays(ctx, code, dry_run, skip_increase):
    apple_music_config = ctx.obj["config"].get(apple_music.LIBRARY_TYPE, {})
    apple_music_library = apple_music.load_library(apple_music_config)
    itunes_config = ctx.obj["config"].get(it.LIBRARY_TYPE, {})
    itunes_library = it.load_library(itunes_config)
    plex_config = ctx.obj["config"].get(pl.LIBRARY_TYPE, {})
    plex_config["code"] = code
    plex_library = pl.load_library(plex_config)
    file_library = ctx.obj["file_library"]
    commands.sync_plays(
        file_library,
        {pl.LIBRARY_TYPE: plex_library, it.LIBRARY_TYPE: itunes_library, apple_music.LIBRARY_TYPE: apple_music_library},
        dry_run=dry_run,
        skip_increase=skip_increase,
    )


@cli.command()
@click.option(
    "--source-type",
    "--from",
    type=click.Choice([it.LIBRARY_TYPE, pl.LIBRARY_TYPE, fl.LIBRARY_TYPE, apple_music.LIBRARY_TYPE]),
    default=fl.LIBRARY_TYPE,
    help=f"Source playlist type (default: {fl.LIBRARY_TYPE})",
)
@click.option(
    "--destination-type",
    "--to",
    type=click.Choice([it.LIBRARY_TYPE, pl.LIBRARY_TYPE, fl.LIBRARY_TYPE, apple_music.LIBRARY_TYPE]),
    default=pl.LIBRARY_TYPE,
    help=f"Destination playlist type (default: {pl.LIBRARY_TYPE})",
)
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.pass_context
def map_tracks(
    ctx,
    source_type: str,
    destination_type: str,
    code: str,
):
    ctx.obj["code"] = code
    src, dest = _src_and_dst(ctx, source_type, destination_type)
    click.echo(f"mapping tracks from {src} to {dest}")

    result = list(dest.map_tracks(src.tracks, dry_run=True))

    click.echo(f"resulting {len(result)} tracks, {len(set(result))} unique")


@cli.command()
@click.option("--shell", "-s", type=click.Choice(["bash", "fish", "zsh"]), required=True, help="Shell to generate completion script for.")
@click.pass_context
def completion(ctx, shell: str):
    """Generate shell completion script."""
    from click.shell_completion import get_completion_class
    comp_class = get_completion_class(shell)
    comp = comp_class(cli, {}, "songchro", "_songchro_COMPLETE")
    click.echo(comp.source())


if __name__ == "__main__":
    cli(obj={})
