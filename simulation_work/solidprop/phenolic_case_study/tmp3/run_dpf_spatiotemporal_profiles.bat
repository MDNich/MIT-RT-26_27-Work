@echo off
setlocal
set "ROOT=C:\Mac\Home\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\solidprop\phenolic_case_study\tmp3"
set "PYTHON=C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe"
set "RESULTS=%ROOT%\testbed2_files\dp0\SYS-3\MECH"

"%PYTHON%" "%ROOT%\dpf_extract_svar_spatiotemporal_profiles.py" ^
  "%ROOT%\docs\analysis\svar_radial_time_profiles_1pct.csv" ^
  "%ROOT%\docs\analysis\svar_axial_time_profiles_1pct.csv" ^
  "%RESULTS%\file0.rth" ^
  "%RESULTS%\file1.rth" ^
  "%RESULTS%\file2.rth" ^
  "%RESULTS%\file3.rth" ^
  "%RESULTS%\file4.rth" ^
  "%RESULTS%\file5.rth" ^
  "%RESULTS%\file6.rth" ^
  "%RESULTS%\file7.rth"

exit /b %ERRORLEVEL%
