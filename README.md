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

## Usage

The `songchro` CLI tool provides commands to work with iTunes and Plex playlists.

### General Commands

```bash
# Show help
songchro --help

# Show version
songchro --version

# Synchronize playlists
songchro sync "My Playlist" 
songchro sync "Source Playlist" "Destination Playlist"
songchro sync "My Playlist" --source-type plex --destination-type itunes
```

### iTunes Commands

```bash
# List iTunes playlists
songchro itunes list

# Export an iTunes playlist
songchro itunes export "My Playlist"
songchro itunes export "My Playlist" --output playlist.json
```

### Plex Commands

```bash
# List Plex playlists
songchro plex list

# Import a playlist to Plex
songchro plex import "My Playlist"
songchro plex import "My Playlist" --input playlist.json
```
