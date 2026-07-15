@echo off
set LOCALHOST=%COMPUTERNAME%
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 11728)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 3720)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 13248)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 3584)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 5104)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 9868)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 6184)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 6900)

del /F cleanup-ansys-MARCDNICHITBF25-6900.bat
