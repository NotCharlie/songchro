on mapTracks(L)
  local mappedTracks
  local newItem
  local trackLocation
  local fpath
  local trackMessages

  using terms from application "Music"
    set mappedTracks to {}
    repeat with aTrack in L
      set trackMessages to {}
      try
        set trackLocation to aTrack's location
        set fpath to the POSIX Path of trackLocation
      on error
        set end of trackMessages to "the file is missing for " & (aTrack's name)
        set fpath to missing value
      end try
      set newItem to {|music_id|: aTrack's database ID, |name|:aTrack's name, |artist|:aTrack's artist, |album|: aTrack's album, |album_artist|: aTrack's album artist, |disc_number|: aTrack's disc number, |track_number|: aTrack's track number, |filepath|: fpath, |playcounts|: aTrack's played count, |messages|: trackMessages}
      set end of mappedTracks to newItem
    end repeat
  end using terms from
  return mappedTracks
end mapTracks

on libraryTracks()
  local allTracks
  tell application "Music"
    set allTracks to every track in it
  end tell
  return mapTracks(allTracks)
end libraryTracks

on playlistTracks(playlistId)
  local allTracks
  tell application "Music"
    set allTracks to every track in playlist id playlistId
  end tell
  return mapTracks(allTracks)
end playlistTracks
