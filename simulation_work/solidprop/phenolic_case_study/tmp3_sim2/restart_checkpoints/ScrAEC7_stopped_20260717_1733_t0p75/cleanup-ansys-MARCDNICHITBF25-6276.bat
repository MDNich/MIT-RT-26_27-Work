@echo off
set LOCALHOST=%COMPUTERNAME%
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 908)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 15352)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 1684)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 5780)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 14236)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 880)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 5184)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 8512)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7496)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 6276)

del /F cleanup-ansys-MARCDNICHITBF25-6276.bat
