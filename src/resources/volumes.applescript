property myMusic: file

on mountMusic(fpath)
  tell application "Finder"
    set myMusic to mount volume fpath
  end tell
end

on unmountMusic()
  tell application "Finder"
    try
      myMusic
      eject disk myMusic
      return "unmounted"
    on error number -2753
      return "not mounted by `mountMusic`"
    end try
end tell
end
