$ErrorActionPreference = "Stop"
$env:ANSYSLMD_LICENSE_FILE = "1055@localhost"
$env:ANS_USE_UPF = ""
$env:ANS_USER_PATH = "C:\ansys_sector_sim2"
$env:ANS_USER_PATH_261 = "C:\ansys_sector_sim2"
$workbench = "C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe"
$project = "C:\ansys_sector_sim2\testbed2.wbpj"
Start-Process -FilePath $workbench -ArgumentList @("-F", $project)
