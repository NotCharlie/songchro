import click

from songchro import model


def list_playlists(library: model.Library, songs: bool, simple: bool) -> None:
    if not simple:
        click.echo(f"Listing {library.source} playlists:")
    for playlist in (
        p for p in library.playlists if not isinstance(p, model.SmartPlaylist)
    ):
        if simple:
            click.echo(playlist.name)
        else:
            click.echo(f"  * {playlist.name}")
            if songs:
                for track in playlist.tracks:
                    click.echo(f"    - {track.name} / {track.artist} / {track.album}")


def export_playlist(source: model.Library, name: str, target: model.Library) -> None:
    click.echo(f"Exporting {source.source} playlist: {name}")
    playlist = source.find_playlist(name)
    if playlist:
        click.echo(f"Found playlist: {name}")
        target.create_playlist(name, playlist.tracks)
    else:
        click.echo(f"No playlist: {name}")


def export_all_playlists(source: model.Library, target: model.Library) -> None:
    click.echo(f"Exporting all {source.source} playlists to {target.source}")
    for playlist in (
        p for p in source.playlists if not isinstance(p, model.SmartPlaylist)
    ):
        target.create_playlist(playlist.name, playlist.tracks)


def import_playlist(
    source: model.Library, name: str, target: model.Library, /, dry_run=False
) -> None:
    click.echo(f"Importing playlist to {target.source} from {source.source} {name}")
    playlist = source.find_playlist(name)
    if playlist:
        click.echo(f"Found playlist: {name}")
        target.create_playlist(name, playlist.tracks, dry_run=dry_run)
        if not dry_run:
            new_playlist = target.find_playlist(name)
            click.echo(f"Created new playlist: {new_playlist.name}")
        else:
            click.echo(f"No new playlist: {name}")
    else:
        click.echo(f"No playlist: {name} in {source.source}")
