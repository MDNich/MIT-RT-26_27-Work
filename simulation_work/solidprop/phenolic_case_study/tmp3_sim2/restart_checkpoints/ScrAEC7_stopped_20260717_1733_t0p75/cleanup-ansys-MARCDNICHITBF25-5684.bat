@echo off
set LOCALHOST=%COMPUTERNAME%
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 8504)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 4484)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 7568)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 15040)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 15132)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 9552)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 15100)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 5948)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 14828)
if /i "%LOCALHOST%"=="MARCDNICHITBF25" (taskkill /f /pid 5684)

del /F cleanup-ansys-MARCDNICHITBF25-5684.bat
