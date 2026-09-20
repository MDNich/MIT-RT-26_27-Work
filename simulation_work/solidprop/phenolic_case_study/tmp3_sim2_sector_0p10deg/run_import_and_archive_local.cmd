@echo off
"C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe" -B -F "C:\ansys_sector_sim2\testbed2.wbpj" -R "C:\ansys_sector_sim2\import_and_archive_local.wbjn" > "C:\ansys_sector_sim2\runwb_output.txt" 2>&1
echo %ERRORLEVEL%> "C:\ansys_sector_sim2\runwb_exitcode.txt"
exit /b %ERRORLEVEL%
