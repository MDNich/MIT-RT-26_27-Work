@echo off
setlocal

if not defined AWP_ROOT261 set "AWP_ROOT261=C:\Program Files\ANSYS Inc\v261"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VSINSTALL="
for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%I"
if not defined VSINSTALL (
  echo Visual Studio 2022 avec les outils C++ x64 est introuvable.
  exit /b 10
)
call "%VSINSTALL%\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 11

set "IFORT_VARS="
for /d %%D in ("%ProgramFiles(x86)%\Intel\oneAPI\compiler\2023.1*") do if exist "%%~fD\env\vars.bat" set "IFORT_VARS=%%~fD\env\vars.bat"
if not defined IFORT_VARS (
  echo Intel oneAPI 2023.1 Classic Fortran est introuvable.
  exit /b 12
)
call "%IFORT_VARS%" intel64 vs2022
if errorlevel 1 exit /b 13

set "INCLUDE=%AWP_ROOT261%\ansys\customize\Include;%INCLUDE%"
set "LIB=%AWP_ROOT261%\ansys\Custom\Lib\winx64;%LIB%"

pushd "%~dp0"
del /q usermatth.obj usermatthLib.dll usermatthLib.lib usermatthLib.exp usermatthLib.map compile.log link.log >nul 2>&1

ifort /DNOSTDCALL /DARGTRAIL /DCADOE_ANSYS /DPCWINNT_SYS /D_EFL /DFORTRAN /O2 /MD /c /fpp /4Yportlib /auto /Fo.\ /watch:source /DPCWIN64_SYS /DPCWINX64_SYS usermatth.F >compile.log 2>&1
if errorlevel 1 goto :CompileError
if not exist usermatth.obj goto :CompileError

>usermatthLibex.def echo EXPORTS
>>usermatthLibex.def echo.
>>usermatthLibex.def echo USERMATTH

>usermatthLib.lrf echo -out:usermatthLib.dll
>>usermatthLib.lrf echo -def:usermatthLibex.def
>>usermatthLib.lrf echo -dll
>>usermatthLib.lrf echo -machine:X64
>>usermatthLib.lrf echo -map
>>usermatthLib.lrf echo -manifest:embed
>>usermatthLib.lrf echo -defaultlib:ANSYS.lib
>>usermatthLib.lrf echo -defaultlib:ansMathUtils.lib
>>usermatthLib.lrf echo -defaultlib:ansMemManager.lib
>>usermatthLib.lrf echo -defaultlib:ansOpenMP.lib
>>usermatthLib.lrf echo -defaultlib:ansUtils.lib
>>usermatthLib.lrf echo usermatth.obj

link @usermatthLib.lrf >link.log 2>&1
if errorlevel 1 goto :LinkError
if not exist usermatthLib.dll goto :LinkError

dumpbin /exports usermatthLib.dll | findstr /I /C:"USERMATTH" >nul
if errorlevel 1 (
  echo La DLL existe, mais l'export USERMATTH est absent.
  popd
  exit /b 22
)

echo usermatthLib.dll a ete construite et l'export USERMATTH a ete verifie.
popd
exit /b 0

:CompileError
echo Echec de compilation. Contenu de compile.log :
type compile.log
popd
exit /b 20

:LinkError
echo Echec de liaison. Contenu de link.log :
type link.log
popd
exit /b 21
