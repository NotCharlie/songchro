# songchro

Synchronize playlists between iTunes and Plex

## Installation

```bash
# Clone the repository
git clone https://github.com/acourtneybrown/songchro.git
cd songchro

# Install the package in development mode
pip install -e .

# Copy .envrc template & modify
cp envrc.template .envrc
vi .envrc
```

## Usage

The `songchro` CLI tool provides commands to work with iTunes and Plex playlists.

### General Commands

```bash
# Show help
songchro --help

# Show version
songchro --version

# Enable debug logging
songchro --debug [COMMAND]

# Synchronize playlists
songchro sync "My Playlist" 
songchro sync "Source Playlist" "Destination Playlist"
songchro sync "My Playlist" --source-type plex --destination-type itunes
```

### iTunes Commands

```bash
# List iTunes playlists
songchro itunes --xml "/path/to/iTunes Library.xml" list
songchro itunes --xml "/path/to/iTunes Library.xml" list --songs

# Export an iTunes playlist
songchro itunes --xml "/path/to/iTunes Library.xml" export "My Playlist"
songchro itunes --xml "/path/to/iTunes Library.xml" export "My Playlist" --output playlist.json

# Export all iTunes playlists
songchro itunes --xml "/path/to/iTunes Library.xml" export_all "/path/to/output/directory"
```

### Plex Commands

```bash
# Authentication options (use one of these methods)
# Method 1: Username, password, and server
songchro plex --username "username" --password "password" --server "server_name" [COMMAND]

# Method 2: Base URL and token
songchro plex --baseurl "http://plex-server:32400" --token "your-plex-token" [COMMAND]

# Method 3: Use default configuration (from environment variables)
songchro plex [COMMAND]

# Specify a different music section (default is "Music")
songchro plex --section "My Music" [COMMAND]

# List Plex playlists
songchro plex list
songchro plex list --songs

# Export a Plex playlist
songchro plex export "My Playlist"
songchro plex export "My Playlist" --output playlist.json

# Export all Plex playlists
songchro plex export_all "/path/to/output/directory"

# Find tracks in Plex
songchro plex find --song-file "/path/to/song.json"
songchro plex find --title "Song Title" --artist "Artist Name"
songchro plex find --album "Album Name" --album-artist "Album Artist"
songchro plex find --filepath "/path/to/music/file.mp3"

# Import a playlist to Plex
songchro plex import "/path/to/playlist.json"
songchro plex import "/path/to/playlist.json" --dry-run
```
