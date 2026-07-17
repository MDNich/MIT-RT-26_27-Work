@echo off
setlocal

if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"
set "SIM2_ROOT=%~dp0"

if not exist "%SIM2_ROOT%usermatthLib.dll" (
  echo Construction de la DLL UserMatTh Simulation 2...
  call "%SIM2_ROOT%build_usermatth_x64.cmd"
  if errorlevel 1 (
    echo La construction de la DLL a echoue.
    pause
    exit /b 1
  )
)

set "ANS_USE_UPF="
set "ANS_USER_PATH=%SIM2_ROOT%"
set "ANS_USER_PATH_261=%SIM2_ROOT%"

start "" "%AWP_ROOT261%\Framework\bin\Win64\RunWB2.exe" -F "%SIM2_ROOT%testbed2.wbpj"
endlocal
