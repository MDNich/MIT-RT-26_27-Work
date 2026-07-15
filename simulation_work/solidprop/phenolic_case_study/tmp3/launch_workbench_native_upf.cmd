@echo off
setlocal

if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"

if not exist "%AWP_ROOT261%\Framework\bin\Win64\RunWB2.exe" (
  echo ANSYS 2026 R1 introuvable sous %AWP_ROOT261%.
  pause
  exit /b 1
)

pushd "%~dp0"

if not exist "%~dp0usermatth.F" (
  echo La source Fortran est introuvable : %~dp0usermatth.F
  popd
  pause
  exit /b 1
)

if not exist "%~dp0usermatthLib.dll" (
  echo Construction de usermatthLib.dll...
  call "%~dp0build_usermatth_x64.cmd"
  if errorlevel 1 (
    popd
    pause
    exit /b 1
  )
)

rem Ne jamais forcer PROCESSOR_ARCHITECTURE ici. Sous Windows 11 ARM64,
rem ANSYS261.exe doit laisser Windows gerer son emulation x64.
set "ANS_USE_UPF="
set "ANS_USER_PATH=%~dp0"
set "ANS_USER_PATH_261=%~dp0"

popd
start "" "%AWP_ROOT261%\Framework\bin\Win64\RunWB2.exe" -F "%~dp0testbed2.wbpj"
endlocal
