@echo off
set LOCALHOST=%COMPUTERNAME%
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 10616)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7204)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 2788)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 17024)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7940)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 16948)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 10704)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 12640)

del /F cleanup-ansys-MARCDNICHITBF25-12640.bat
