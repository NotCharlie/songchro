#!/usr/bin/env python3
"""
CLI interface for songchro using Click.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict

import click
import structlog

import songchro.itunes as it
import songchro.plex as pl
from songchro import __version__
from songchro import file_library
from songchro import model


@click.group()
@click.version_option(version=__version__)
@click.option("--debug", is_flag=True)
@click.option("--info", is_flag=True)
@click.option(
    "--music_root",
    type=click.Path(),
    default=None,
    help="Path to Music root.  Will be stripped in resulting playlist files.",
)
@click.pass_context
def cli(ctx, debug: bool, info: bool, music_root: str):
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
    ctx.obj["music_root"] = music_root if music_root else "/"


@cli.group()
@click.pass_context
@click.option(
    "--local-root",
    type=click.Path(exists=True),
    help="Root directory for local playlist files.",
)
def local(ctx, local_root: str):
    music_root = ctx.obj["music_root"]
    ctx.obj["local_library"] = file_library.load_library(local_root, music_root)


@local.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show all songs.")
def local_list(ctx, songs: bool):
    library = ctx.obj["local_library"]
    click.echo("Listing local playlists:")
    for playlist in (
        p for p in library.playlists if not isinstance(p, model.SmartPlaylist)
    ):
        click.echo(f"  * {playlist.name}")
        if songs:
            for track in playlist.tracks:
                click.echo(f"    - {track.name} / {track.artist} / {track.album}")


@cli.group()
@click.pass_context
@click.option(
    "--xml",
    "-x",
    required=True,
    type=click.Path(exists=True),
    help="Path to iTunes Library xml file.",
)
def itunes(ctx, xml: str):
    """Commands for working with iTunes playlists."""
    music_root = ctx.obj["music_root"]
    ctx.obj["itunes_library"] = it.load_library(xml, music_root)


@itunes.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
def itunes_list(ctx, songs: bool):
    """List available iTunes playlists."""
    library = ctx.obj["itunes_library"]
    click.echo("Listing iTunes playlists:")
    for playlist in (
        p for p in library.playlists if not isinstance(p, model.SmartPlaylist)
    ):
        click.echo(f"  * {playlist.name}")
        if songs:
            for track in playlist.tracks:
                click.echo(f"    - {track.name} / {track.artist} / {track.album}")


@itunes.command("export")
@click.argument("playlist_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path. Default <playlist_name>.json",
)
@click.pass_context
def itunes_export(ctx, playlist_name: str, output: str):
    """Export an iTunes playlist."""
    click.echo(f"Exporting iTunes playlist: {playlist_name}")
    if not output:
        output = playlist_name + ".json"
    click.echo(f"Output file: {output}")
    library = ctx.obj["itunes_library"]
    playlist = library.find_playlist(playlist_name)
    if playlist:
        click.echo(f"Found playlist: {playlist.name}")
        with open(output, "w") as f:
            f.write(playlist.to_json())
    else:
        click.echo(f"No playlist: {playlist_name}")


@itunes.command("export_all")
@click.argument("output_dir", type=click.Path())
@click.pass_context
def itunes_export_all(ctx, output_dir: str):
    click.echo(f"Exporting all iTunes playlists: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    library = ctx.obj["itunes_library"]
    for playlist in library.playlists:
        with open(os.path.join(output_dir, f"{playlist.name}.json"), "w") as f:
            click.echo(f"Exporting playlist: {playlist.name}")
            f.write(playlist.to_json())


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
):
    """Commands for working with Plex playlists."""
    music_root = ctx.obj["music_root"]
    if username and password and server:
        ctx.obj["plex_library"] = pl.load_library_by_username(
            username, password, code, server, music_root, section=section
        )
    elif baseurl and token:
        ctx.obj["plex_library"] = pl.load_library_by_baseurl(
            baseurl, token, music_root, section=section
        )
    else:
        ctx.obj["plex_library"] = pl.load_library(music_root, section=section)


@plex.command("list")
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
@click.pass_context
def plex_list(ctx, songs: bool):
    """List available Plex playlists."""
    click.echo("Listing Plex playlists")
    library = ctx.obj["plex_library"]
    for playlist in library.playlists:
        click.echo(f"  * {playlist.name}")
        if songs:
            for track in playlist.tracks:
                click.echo(f"    - {track.name} / {track.artist} / {track.album}")


@plex.command("export")
@click.argument("playlist_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path. Default <playlist_name>.json",
)
@click.pass_context
def plex_export(ctx, playlist_name: str, output: str):
    """Export a Plex playlist."""
    click.echo(f"Exporting Plex playlist: {playlist_name}")
    if not output:
        output = playlist_name + ".json"
    click.echo(f"Output file: {output}")
    library = ctx.obj["plex_library"]
    playlist = library.find_playlist(playlist_name)
    if playlist:
        click.echo(f"Found playlist: {playlist.name}")
        with open(output, "w") as f:
            f.write(playlist.to_json())
    else:
        click.echo(f"No playlist: {playlist_name}")


@plex.command("export_all")
@click.argument("output_dir", type=click.Path())
@click.pass_context
def plex_export_all(ctx, output_dir: str):
    click.echo(f"Exporting all Plex playlists: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    library = ctx.obj["plex_library"]
    for playlist in library.playlists:
        with open(os.path.join(output_dir, f"{playlist.name}.json"), "w") as f:
            click.echo(f"Exporting playlist: {playlist.name}")
            f.write(playlist.to_json())


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
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
@click.pass_context
def plex_import(ctx, input_file: str, dry_run: bool):
    """Import a playlist to Plex."""
    library = ctx.obj["plex_library"]
    click.echo(f"Importing playlist to Plex: from {input_file}")
    with open(input_file, "r") as f:
        to_import = json.load(f)
        playlist_name = to_import["name"]
        tracks = [model.Track(**track) for track in to_import.get("tracks", [])]
    click.echo(f"Found playlist: {playlist_name} {len(tracks)} tracks")
    library.create_playlist(playlist_name, tracks, dry_run=dry_run)
    if not dry_run:
        new_playlist = library.find_playlist(playlist_name)
        click.echo(f"Created new playlist: {new_playlist.name}")
    else:
        click.echo(f"No new playlist: {playlist_name}")


@cli.command()
@click.argument("playlist")
@click.option(
    "--source-type",
    type=click.Choice(["itunes", "plex", "local"]),
    default="local",
    help="Source playlist type (default: local)",
)
@click.option(
    "--itunes-music-root",
    type=click.Path(),
    help="Root directory for iTunes media files.",
)
@click.option(
    "--destination-type",
    type=click.Choice(["itunes", "plex", "local"]),
    default="plex",
    help="Destination playlist type (default: plex)",
)
@click.option(
    "--plex-music-root",
    type=click.Path(),
    help="Root directory for Plex media files.",
)
@click.option(
    "--xml",
    "-x",
    type=click.Path(exists=True),
    help="Path to iTunes Library xml file.  Required if source-type or destination-type is itunes.",
)
@click.option(
    "--local-root",
    type=click.Path(exists=True),
    help="Root directory for local playlist files.",
)
@click.option(
    "--local-music-root",
    type=click.Path(),
    help="Root directory for local media files.",
)
@click.option("--dry-run", "-d", is_flag=True, help="Dry run.")
def sync(
    playlist: str,
    source_type: str,
    itunes_music_root: str,
    destination_type: str,
    plex_music_root: str,
    xml: str,
    local_root: str,
    local_music_root: str,
    dry_run: bool,
):
    """Synchronize playlists between platforms."""

    click.echo(
        f"Syncing from {source_type} to {destination_type} for playlist '{playlist}' "
    )
    libs: Dict[str, model.Library] = {}
    if source_type == "itunes" or destination_type == "itunes":
        itunes_library = it.load_library(xml, itunes_music_root)
        libs["itunes"] = itunes_library
    if source_type == "plex" or destination_type == "plex":
        plex_library = pl.load_library(plex_music_root)
        libs["plex"] = plex_library
    if source_type == "local" or destination_type == "local":
        local_library = file_library.load_library(local_root, local_music_root)
        libs["local"] = local_library

    src = libs[source_type].find_playlist(playlist)
    dest = libs[destination_type].find_playlist(playlist)

    click.echo(f"Syncing from {src} to {dest}...")
    dest.sync_tracks(src, dry_run=dry_run)


if __name__ == "__main__":
    cli(obj={})
