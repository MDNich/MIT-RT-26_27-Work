@echo off
setlocal
if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"
pushd "%~dp0"
del /q verify_continue.* verify_multiframe_values.txt verify_multiframe_continue.out >nul 2>&1
"%AWP_ROOT261%\ansys\bin\winx64\ANSYS261.exe" -b -p ansys -np 1 -dir "%~dp0" -j verify_continue -i verify_multiframe_continue.dat -o verify_multiframe_continue.out
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Echec du test multiframe, code %RC%.
  popd
  exit /b %RC%
)
findstr /C:"NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0" verify_multiframe_continue.out >nul
if errorlevel 1 (
  echo Le test multiframe a signale au moins une erreur.
  findstr /I /C:"error" /C:"fatal" verify_multiframe_continue.out
  popd
  exit /b 40
)
findstr /C:"VERIFY_MULTIFRAME_CONTINUE_COMPLETED" verify_multiframe_continue.out >nul
if errorlevel 1 (
  echo Le test multiframe n'a pas atteint sa fin normale.
  popd
  exit /b 41
)
type verify_multiframe_values.txt
popd
exit /b 0
