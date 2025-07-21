#!/usr/bin/env python3
"""
CLI interface for songchro using Click.
"""

import click

import songchro.itunes as it
import songchro.plex as pl
from . import __version__


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """Synchronize playlists between iTunes and Plex."""
    ctx.ensure_object(dict)


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
    ctx.obj["itunes_library"] = it.load_library(xml)


@itunes.command("list")
@click.pass_context
@click.option("--songs", "-s", is_flag=True, help="Show songs list.")
def itunes_list(ctx, songs: bool):
    """List available iTunes playlists."""
    library = ctx.obj["itunes_library"]
    click.echo("Listing iTunes playlists:")
    for playlist in library.playlists:
        click.echo(f"  * {playlist.name}")
        if songs:
            for track in playlist.tracks:
                click.echo(f"    - {track.name} / {track.artist} / {track.album}")


@itunes.command("export")
@click.argument("playlist_name")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def itunes_export(ctx, playlist_name: str, output: str):
    """Export an iTunes playlist."""
    click.echo(f"Exporting iTunes playlist: {playlist_name}")
    if output:
        click.echo(f"Output file: {output}")
        library = ctx.obj["itunes_library"]
        playlist = library.find_playlist(playlist_name)
        if playlist:
            click.echo(f"Found playlist: {playlist.name}")
            with open(output, "w") as f:
                f.write(playlist.to_json())
        else:
            click.echo(f"No playlist: {playlist_name}")


@cli.group()
@click.option(
    "--username",
    "-u",
    type=str,
    help="Username for Plex account.",
)
@click.option("--password", "-p", type=str, help="Password for Plex account.")
@click.option("--server", "-s", type=str, help="Plex server name.")
@click.option("--baseurl", "-b", type=str, help="Base URL for Plex server.")
@click.option("--token", "-t", type=str, help="Plex API token.")
@click.option(
    "--section", type=str, help="Plex section name for Music library.", default="Music"
)
@click.pass_context
def plex(ctx, username, password, server, baseurl, token, section):
    """Commands for working with Plex playlists."""
    if username and password and server:
        ctx.obj["plex_library"] = pl.load_library_by_username(
            username, password, server, section
        )
    elif baseurl and token:
        ctx.obj["plex_library"] = pl.load_library_by_baseurl(baseurl, token, section)
    else:
        ctx.obj["plex_library"] = pl.load_library(section=section)


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
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def plex_export(ctx, playlist_name: str, output: str):
    """Export an Plex playlist."""
    click.echo(f"Exporting Plex playlist: {playlist_name}")
    if output:
        click.echo(f"Output file: {output}")
        library = ctx.obj["plex_library"]
        playlist = library.find_playlist(playlist_name)
        if playlist:
            click.echo(f"Found playlist: {playlist.name}")
            with open(output, "w") as f:
                f.write(playlist.to_json())
        else:
            click.echo(f"No playlist: {playlist_name}")


@plex.command("import")
@click.argument("playlist_name")
@click.option("--input", "-i", type=click.Path(exists=True), help="Input file path")
@click.pass_context
def plex_import(ctx, playlist_name, input):
    """Import a playlist to Plex."""
    click.echo(f"Importing playlist to Plex: {playlist_name} (not implemented yet)")
    if input:
        click.echo(f"Input file: {input}")


@cli.command()
@click.argument("source_playlist")
@click.argument("destination_playlist", required=False)
@click.option(
    "--source-type",
    type=click.Choice(["itunes", "plex"]),
    default="itunes",
    help="Source playlist type (default: itunes)",
)
@click.option(
    "--destination-type",
    type=click.Choice(["itunes", "plex"]),
    default="plex",
    help="Destination playlist type (default: plex)",
)
def sync(source_playlist, destination_playlist, source_type, destination_type):
    """Synchronize playlists between platforms.

    If DESTINATION_PLAYLIST is not provided, the SOURCE_PLAYLIST name will be used.
    """
    if not destination_playlist:
        destination_playlist = source_playlist

    click.echo(
        f"Syncing from {source_type} playlist '{source_playlist}' "
        f"to {destination_type} playlist '{destination_playlist}' "
        f"(not implemented yet)"
    )


if __name__ == "__main__":
    cli(obj={})
