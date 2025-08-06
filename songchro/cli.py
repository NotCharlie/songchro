#!/usr/bin/env python3
"""
CLI interface for songchro using Click.
"""
import json
import logging
import os
from pathlib import Path

import click
import structlog

import songchro.file_library as fl
import songchro.itunes as it
import songchro.plex as pl
from songchro import __version__, commands
from songchro import model


@click.group()
@click.version_option(version=__version__)
@click.option("--debug", is_flag=True)
@click.option("--info", is_flag=True)
@click.option(
    "--file-music-root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Root directory for local media files.  Will be stripped in resulting playlist files.",
)
@click.option(
    "--file-root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Root directory for local playlist files.",
)
@click.pass_context
def cli(ctx, debug: bool, info: bool, file_root: str, file_music_root: str):
    """Synchronize playlists between iTunes and Plex."""
    ctx.ensure_object(dict)
    if debug:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
        )
    elif info:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
        )
    else:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
        )
    ctx.obj["file_library"] = fl.load_library(file_root, file_music_root)


@cli.group()
@click.pass_context
def file(ctx):
    pass


@file.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show all songs.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
def file_list(ctx, songs: bool, simple: bool):
    library = ctx.obj["file_library"]
    commands.list_playlists(library, songs, simple)


@cli.group()
@click.pass_context
@click.option(
    "--xml",
    "-x",
    required=True,
    type=click.Path(exists=True),
    help="Path to iTunes Library xml file.",
)
@click.option(
    "--itunes-music-root",
    type=click.Path(),
    help="Root directory for iTunes media files.",
)
def itunes(ctx, xml: str, itunes_music_root: str):
    """Commands for working with iTunes playlists."""
    ctx.obj["itunes_library"] = it.load_library(xml, itunes_music_root)


@itunes.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
def itunes_list(ctx, songs: bool, simple: bool):
    """List available iTunes playlists."""
    library = ctx.obj["itunes_library"]
    commands.list_playlists(library, songs, simple)


@itunes.command("export")
@click.argument("playlist_name")
@click.pass_context
def itunes_export(ctx, playlist_name: str):
    """Export an iTunes playlist to the local library."""
    file_library = ctx.obj["file_library"]
    library = ctx.obj["itunes_library"]
    commands.export_playlist(library, playlist_name, file_library)


@itunes.command("export_all")
@click.pass_context
def itunes_export_all(ctx):
    file_library = ctx.obj["file_library"]
    library = ctx.obj["itunes_library"]
    commands.export_all_playlists(library, file_library)


@cli.group()
@click.option(
    "--username",
    "-u",
    type=str,
    help="Username for Plex account.",
)
@click.option("--password", "-p", type=str, help="Password for Plex account.")
@click.option("--code", "-c", type=str, help="OTP code for Plex account.")
@click.option("--server", "-s", type=str, help="Plex server name.")
@click.option("--baseurl", "-b", type=str, help="Base URL for Plex server.")
@click.option("--token", "-t", type=str, help="Plex API token.")
@click.option(
    "--section", type=str, help="Plex section name for Music library.", default="Music"
)
@click.option("--plex-music-root", type=click.Path(), help="Plex music root path.")
@click.pass_context
def plex(
    ctx,
    username: str,
    password: str,
    code: str,
    server: str,
    baseurl: str,
    token: str,
    section: str,
    plex_music_root,
):
    """Commands for working with Plex playlists."""
    if username and password and server:
        ctx.obj["plex_library"] = pl.load_library_by_username(
            username, password, code, server, plex_music_root, section=section
        )
    elif baseurl and token:
        ctx.obj["plex_library"] = pl.load_library_by_baseurl(
            baseurl, token, plex_music_root, section=section
        )
    else:
        ctx.obj["plex_library"] = pl.load_library(plex_music_root, section=section)


@plex.command("list")
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.option("--simple", is_flag=True, help="Simple format, useful for pipelining.")
@click.pass_context
def plex_list(ctx, songs: bool, simple: bool):
    """List available Plex playlists."""
    library = ctx.obj["plex_library"]
    commands.list_playlists(library, songs, simple)


@plex.command("export")
@click.argument("playlist_name")
@click.pass_context
def plex_export(ctx, playlist_name: str):
    """Export a Plex playlist to the local library."""
    file_library = ctx.obj["file_library"]
    library = ctx.obj["plex_library"]
    commands.export_playlist(library, playlist_name, file_library)


@plex.command("export_all")
@click.pass_context
def plex_export_all(ctx):
    file_library = ctx.obj["file_library"]
    plex_library = ctx.obj["plex_library"]
    commands.export_all_playlists(plex_library, file_library)


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
    music_root = ctx.obj["music_root"]
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
            filepath=Path(os.path.relpath(filepath, start=music_root)),
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
    type=click.Choice(["itunes", "plex", "file"]),
    default="file",
    help="Source playlist type (default: file)",
)
@click.option(
    "--destination-type",
    type=click.Choice(["itunes", "plex", "file"]),
    default="plex",
    help="Destination playlist type (default: plex)",
)
@click.option(
    "--xml",
    "-x",
    type=click.Path(exists=True),
    help="Path to iTunes Library xml file.  Required if source-type or destination-type is itunes.",
)
@click.option(
    "--itunes-music-root",
    type=click.Path(),
    help="Root directory for iTunes media files.",
)
@click.option(
    "--plex-music-root",
    type=click.Path(),
    help="Root directory for Plex media files.",
)
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def sync(
    ctx,
    playlist: str,
    source_type: str,
    destination_type: str,
    xml: str,
    itunes_music_root: str,
    plex_music_root: str,
    dry_run: bool,
):
    """Synchronize playlists between platforms."""

    click.echo(
        f"Syncing from {source_type} to {destination_type} for playlist '{playlist}' "
    )
    libs: dict[str, model.Library] = {}
    if source_type == "itunes" or destination_type == "itunes":
        itunes_library = it.load_library(xml, itunes_music_root)
        libs["itunes"] = itunes_library
    if source_type == "plex" or destination_type == "plex":
        plex_library = pl.load_library(plex_music_root)
        libs["plex"] = plex_library
    if source_type == "file" or destination_type == "file":
        file_library = ctx.obj["file_library"]
        libs["file"] = file_library

    src = libs[source_type].find_playlist(playlist)
    dest = libs[destination_type].find_playlist(playlist)

    click.echo(f"Syncing from {src} to {dest}...")
    dest.sync_tracks(src, dry_run=dry_run)


if __name__ == "__main__":
    cli(obj={})
