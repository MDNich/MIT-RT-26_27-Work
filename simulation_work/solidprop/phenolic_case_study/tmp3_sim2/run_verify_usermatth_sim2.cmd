@echo off
setlocal
if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"
set "ANS_USER_PATH=%~dp0"
pushd "%~dp0"
del /q verify_sim2.* verify_usermatth_values.txt >nul 2>&1
"%AWP_ROOT261%\ansys\bin\winx64\ANSYS261.exe" -b -p ansys -np 1 -dir "%~dp0" -j verify_sim2 -i verify_usermatth_sim2.dat -o verify_usermatth_sim2.out
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Echec du coupon MAPDL, code %RC%.
  popd
  exit /b %RC%
)
findstr /C:"NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0" verify_usermatth_sim2.out >nul
if errorlevel 1 (
  echo MAPDL a signale au moins une erreur.
  findstr /I /C:"error" /C:"fatal" verify_usermatth_sim2.out
  popd
  exit /b 30
)
echo Coupon MAPDL termine avec zero erreur.
type verify_usermatth_values.txt
popd
exit /b 0
