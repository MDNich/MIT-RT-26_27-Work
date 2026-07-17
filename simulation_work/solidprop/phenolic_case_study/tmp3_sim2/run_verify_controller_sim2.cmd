@echo off
setlocal
if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"
set "ANS_USER_PATH=%~dp0"
pushd "%~dp0"
del /q verify_controller.* simulation2_history.csv simulation2_state.parm simulation2_iteration.txt >nul 2>&1
"%AWP_ROOT261%\ansys\bin\winx64\ANSYS261.exe" -b -p ansys -np 1 -dir "%~dp0" -j verify_controller -i verify_controller_sim2.dat -o verify_controller_sim2.out
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Echec du controleur MAPDL, code %RC%.
  popd
  exit /b %RC%
)
findstr /C:"NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0" verify_controller_sim2.out >nul
if errorlevel 1 (
  echo Le controleur MAPDL a signale au moins une erreur.
  findstr /I /C:"error" /C:"fatal" verify_controller_sim2.out
  popd
  exit /b 30
)
findstr /C:"SIM2 multiframe controller completed" verify_controller_sim2.out >nul
if errorlevel 1 (
  echo Le controleur n'a pas atteint sa fin normale.
  popd
  exit /b 31
)
echo Controleur MAPDL termine avec zero erreur.
type simulation2_history.csv
popd
exit /b 0
