from pathlib import Path
import subprocess,sys
p=Path(sys.argv[1]).resolve(); win='Z:'+str(p).split('/Users/mdn',1)[1].replace('/','\\')
ps=p.with_suffix('.launch.ps1');ps.write_text("& 'C:\\Program Files\\ANSYS Inc\\v261\\commonfiles\\IronPython\\ipy64.exe' '"+win+"'\n")
w='Z:'+str(ps).split('/Users/mdn',1)[1].replace('/','\\')
r=subprocess.run(['prlctl','exec','{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}','--current-user','powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',w]);sys.exit(r.returncode)
