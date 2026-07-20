@echo off
set LOCALHOST=%COMPUTERNAME%
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7416)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 8908)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 16148)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7852)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 6200)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 12764)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 12904)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 3984)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 6264)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 3868)

del /F cleanup-ansys-MARCDNICHITBF25-3868.bat
