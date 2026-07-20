@echo off
setlocal EnableExtensions

if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"

pushd "%~dp0"
set "SIM2_ROOT=%CD%"
set "RUN_DIR=%SIM2_ROOT%\resume_runs\RestartProbe_step16_20260719"

set "ANS_USE_UPF="
set "ANS_USER_PATH=%SIM2_ROOT%"
set "ANS_USER_PATH_261=%SIM2_ROOT%"

pushd "%RUN_DIR%"
del /q combine_rth.out >nul 2>&1

"%AWP_ROOT261%\ansys\bin\winx64\ANSYS261.exe" -b nolist -p ansys -dis -mpi intelmpi -np 10 -dir "%RUN_DIR%" -j file -s noread -i simulation2_combine_rth.apdl -o combine_rth.out
set "RC=%ERRORLEVEL%"

>simulation2_combine_rth_exit_code.txt echo %RC%
popd
popd
exit /b %RC%
