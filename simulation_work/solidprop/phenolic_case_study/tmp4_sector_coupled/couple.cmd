@echo off
"C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe" "C:\ansys_sector_iter4\coupler.py" %1 --root "C:\ansys_sector_iter4"
exit /b %ERRORLEVEL%
