@echo off
setlocal
rem Run in an isolated Iris build directory containing usermatth.F.
rem Compiler/link options follow the installed v261 ANSUSERSHARED.bat.
call "C:\Program Files (x86)\Intel\oneAPI\compiler\2023.1.0\env\vars.bat" intel64 vs2022
if errorlevel 1 exit /b 1
set "INCLUDE=C:\Program Files\ANSYS Inc\v261\ansys\customize\Include;%INCLUDE%"
set "LIB=C:\Program Files\ANSYS Inc\v261\ansys\custom\lib\winx64;%LIB%"
ifort /DNOSTDCALL /DARGTRAIL /DCADOE_ANSYS /DPCWINNT_SYS /D_EFL /DFORTRAN /O2 /MD /c /fpp /4Yportlib /auto /Fo.\ /watch:source /DPCWIN64_SYS /DPCWINX64_SYS usermatth.F > compile.log 2>&1
if errorlevel 1 exit /b 1
link /out:usermatthLib.dll /def:usermatthLibex.def /dll /machine:X64 /map /manifest:embed /defaultlib:ANSYS.lib /defaultlib:ansMathUtils.lib /defaultlib:ansMemManager.lib /defaultlib:ansOpenMP.lib /defaultlib:ansUtils.lib usermatth.obj > link.log 2>&1
if errorlevel 1 exit /b 1
dumpbin /exports /dependents usermatthLib.dll > binary_inspection.log 2>&1
exit /b %errorlevel%
