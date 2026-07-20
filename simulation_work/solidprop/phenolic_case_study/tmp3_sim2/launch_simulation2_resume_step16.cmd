@echo off
setlocal EnableExtensions

if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"

pushd "%~dp0"
set "SIM2_ROOT=%CD%"
set "RUN_DIR=%SIM2_ROOT%\resume_runs\ScrResume_step16_v2_20260719"

if not exist "%SIM2_ROOT%\usermatthLib.dll" (
  echo ERROR: usermatthLib.dll is missing.
  popd
  exit /b 20
)
if not exist "%RUN_DIR%\file0.r001" (
  echo ERROR: distributed restart files are missing from %RUN_DIR%.
  popd
  exit /b 21
)
if not exist "%RUN_DIR%\simulation2_resume_step16.apdl" (
  echo ERROR: the recovery input file is missing from %RUN_DIR%.
  popd
  exit /b 22
)

set "ANS_USE_UPF="
set "ANS_USER_PATH=%SIM2_ROOT%"
set "ANS_USER_PATH_261=%SIM2_ROOT%"

pushd "%RUN_DIR%"
del /q file.abt simulation2_stop.request resume_solve.out >nul 2>&1

"%AWP_ROOT261%\ansys\bin\winx64\ANSYS261.exe" -b nolist -p ansys -dis -mpi intelmpi -np 10 -dir "%RUN_DIR%" -j file -s noread -i simulation2_resume_step16.apdl -o resume_solve.out
set "RC=%ERRORLEVEL%"

>simulation2_resume_exit_code.txt echo %RC%
popd
popd
exit /b %RC%
