on mapPlaylists(L)
  local mappedPlaylists
  local newItem
  local parentId

  using terms from application "Music"
    set mappedPlaylists to {}
    repeat with aPlaylist in L
      set parentId to -1
      try
        set parentId to aPlaylist's parent's id
      end try
      set newItem to {|name|:aPlaylist's name, |music_id|:aPlaylist's id, |parent_id|:parentId, |smart|:aPlaylist's smart}
      set end of mappedPlaylists to newItem
    end repeat
    return mappedPlaylists
  end using terms from
end mapPlaylists

on listPlaylists()
  tell application "Music"
    local allPlaylists
    set allPlaylists to every user playlist whose special kind is none and smart is False
  end tell
  return mapPlaylists(allPlaylists)
end listPlaylists

on listFolderPlaylists()
  tell application "Music"
    local allPlaylists
    set allPlaylists to every folder playlist
  end tell
  return mapPlaylists(allPlaylists)
end listFolderPlaylists

on listSmartPlaylists()
  tell application "Music"
    local allPlaylists
    set allPlaylists to every user playlist whose special kind is none and smart is True
  end tell
  return mapPlaylists(allPlaylists)
end listSmartPlaylists
