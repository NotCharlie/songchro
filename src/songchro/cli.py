#!/usr/bin/env python3
"""
CLI interface for songchro using Click.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

import click
import structlog
import yaml

import songchro.file_library as fl
import songchro.itunes as it
import songchro.plex as pl
from songchro import __version__
from songchro import commands
from songchro import model
from songchro.plex import PlexLibrary


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
    type=click.Path(exists=True, dir_okay=False),
    default=os.path.expanduser("~/.config/songchro/config.yml"),
    help="Configuration file.",
)
@click.pass_context
def cli(ctx, logging_level: str, config_file: str):
    """Synchronize playlists between iTunes and Plex."""
    ctx.ensure_object(dict)
    with open(os.path.expanduser(config_file), "r") as f:
        ctx.obj["config"] = config = yaml.safe_load(f)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(logging_level or config.get("logging", "WARNING")),
        )
    )

    file_config = config.get("file", {})
    ctx.obj["file_library"] = fl.load_library(
        os.path.expanduser(file_config.get("root")),
        os.path.expanduser(file_config.get("music_root")),
    )


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


@cli.group()
@click.pass_context
def itunes(ctx):
    """Commands for working with iTunes playlists."""
    itunes_config = ctx.obj["config"].get("itunes", {})
    ctx.obj["itunes_library"] = it.load_library(
        os.path.expanduser(itunes_config.get("xml")),
        os.path.expanduser(itunes_config.get("music_root")),
    )


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


def _load_plex_from_config(plex_config: dict[str, Any], code: str) -> PlexLibrary:
    plex_music_root = plex_config.get("music_root")
    section = plex_config.get("section")

    username = plex_config.get("username")
    password = plex_config.get("password")
    server = plex_config.get("server")
    baseurl = plex_config.get("baseurl")
    token = plex_config.get("token")
    if username and password and server:
        return pl.load_library_by_username(
            username, password, code, server, plex_music_root, section=section
        )
    elif baseurl and token:
        return pl.load_library_by_baseurl(
            baseurl, token, plex_music_root, section=section
        )
    return pl.load_library(plex_music_root, section=section)


@cli.group()
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.pass_context
def plex(
    ctx,
    code: str,
):
    """Commands for working with Plex playlists."""
    plex_config = ctx.obj["config"].get("plex", {})
    ctx.obj["plex_library"] = _load_plex_from_config(plex_config, code)


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
@click.option(
    "--song-file", "--s", type=click.Path(exists=True), help="Song file json."
)
@click.option("--title", "-t", type=str, default="", help="Search title.")
@click.option("--artist", "-ar", type=str, default="", help="Search artist.")
@click.option("--album", "-al", type=str, default="", help="Search album.")
@click.option(
    "--album-artist", "-aa", type=str, default="", help="Search album artist."
)
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
            filepath=Path(os.path.relpath(filepath, start=library.music_root)),
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


@cli.command()
@click.argument("playlist")
@click.option(
    "--source-type",
    "--from",
    type=click.Choice(["itunes", "plex", "file"]),
    default="file",
    help="Source playlist type (default: file)",
)
@click.option(
    "--destination-type",
    "--to",
    type=click.Choice(["itunes", "plex", "file"]),
    default="plex",
    help="Destination playlist type (default: plex)",
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

    click.echo(
        f"Syncing from {source_type} to {destination_type} for playlist '{playlist}' "
    )
    libs: dict[str, model.Library] = {}
    if source_type == "itunes" or destination_type == "itunes":
        itunes_config = ctx.obj["config"].get("itunes", {})
        libs["itunes"] = it.load_library(
            os.path.expanduser(itunes_config.get("xml")),
            os.path.expanduser(itunes_config.get("music_root")),
        )
    if source_type == "plex" or destination_type == "plex":
        plex_config = ctx.obj["config"].get("plex", {})
        libs["plex"] = _load_plex_from_config(plex_config, code)
    if source_type == "file" or destination_type == "file":
        libs["file"] = ctx.obj["file_library"]

    src = libs[source_type].find_playlist(playlist)
    dest = libs[destination_type].find_playlist(playlist)

    click.echo(f"Syncing from {src} to {dest}...")
    dest.sync_tracks(src, dry_run=dry_run)


if __name__ == "__main__":
    cli(obj={})
