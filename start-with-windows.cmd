@echo off
rem Put a shortcut to Pip in your Startup folder.
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'Pip.lnk'));" ^
  "$s.TargetPath=(Get-Command pythonw).Source;" ^
  "$s.Arguments='\"%~dp0deskpet.py\"';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.Save(); Write-Host 'Added Pip to Startup.'"
pause
