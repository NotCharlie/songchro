# songchro

Synchronize playlists between iTunes and Plex

## Installation

```bash
# Clone the repository
git clone https://github.com/acourtneybrown/songchro.git
cd songchro

# Install the package in development mode
pip install -e .
```

## Configuration

Songchro uses a configuration file located at `~/.config/songchro/config.yml`. This file contains settings for the different music libraries and general options.

### Configuration File Structure

```yaml
# Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging: INFO

# File library configuration
file:
  # Root directory for playlist files
  root: ~/playlists
  # Root directory for music files
  music_root: ~/Music

# iTunes library configuration
itunes:
  # Path to iTunes Library XML file
  xml: ~/Music/iTunes/iTunes Library.xml
  # Root directory for music files
  music_root: ~/Music/iTunes/iTunes Media/Music

# Plex library configuration
plex:
  # Root directory for music files
  music_root: /music
  # Plex music section name (default is "Music")
  section: Music
  # Authentication options (use either username/password/server or baseurl/token)
  username: your_username
  password: your_password
  server: your_server_name
  # Alternative authentication
  baseurl: http://plex-server:32400
  token: your_plex_token
```

## Usage

The `songchro` CLI tool provides commands to work with iTunes, Plex, and local file playlists.

### General Commands

```bash
# Show help
songchro --help

# Show version
songchro --version

# Enable debug level logging
songchro --logging-level DEBUG [COMMAND]

# Enable info level logging
songchro --logging-level INFO [COMMAND]

# Use a specific config file
songchro --config /path/to/config.yml [COMMAND]
```

### File Commands

```bash
# List file playlists
songchro file list

# Include list of song tracks in each playlist
songchro file list --songs

# Simplified output for using in pipelines
songchro file list --simple
```

### iTunes Commands

```bash
# List iTunes playlists
songchro itunes list

# Include list of song tracks in each playlist
songchro itunes list --songs

# Simplified output for using in pipelines
songchro itunes list --simple

# Export an iTunes playlist
songchro itunes export "My Playlist"

# Export all iTunes playlists
songchro itunes export_all
```

### Plex Commands

```bash
# List Plex playlists
songchro plex list

# Include list of song tracks in each playlist
songchro plex list --songs

# Simplified output for using in pipelines
songchro plex list --simple

# Export a Plex playlist
songchro plex export "My Playlist"

# Export all Plex playlists
songchro plex export_all

# Find tracks in Plex
songchro plex find --song-file "/path/to/song.json"
songchro plex find --title "Song Title" --artist "Artist Name"
songchro plex find --album "Album Name" --album-artist "Album Artist"
songchro plex find --filepath "/path/to/music/file.mp3"

# Import a playlist to Plex
songchro plex import "My Playlist"
songchro plex import "My Playlist" --dry-run

# Use OTP code for Plex authentication
songchro plex --code "123456" [COMMAND]
```

### Sync playlists

```bash
# Synchronize playlists
songchro sync "My Playlist" 

# Specify source and destination types
songchro sync "My Playlist" --source-type plex --destination-type file
songchro sync "My Playlist" --from plex --to file

# Dry run (no changes)
songchro sync "My Playlist" --dry-run

# Use OTP code for Plex authentication
songchro sync "My Playlist" --code "123456"
```