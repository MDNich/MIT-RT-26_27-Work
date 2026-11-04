@echo off
"C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe" "C:\IrisStudy\runs\sustainer_al_pulse7_n80_midpoint_tight\coupler.py" %1 --root "C:\IrisStudy\runs\sustainer_al_pulse7_n80_midpoint_tight"
exit /b %ERRORLEVEL%
