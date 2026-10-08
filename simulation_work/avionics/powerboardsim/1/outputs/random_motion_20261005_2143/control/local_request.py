from pathlib import Path
import sys,subprocess,datetime
T=Path(__file__).resolve().parents[1];P=T.parents[1];src=Path(sys.argv[1]).resolve();assert src.exists()
win=r'\\Mac\Home'+str(src).split('/Users/mdn',1)[1].replace('/','\\')
ps="""$ErrorActionPreference='Stop'
$root='C:\\Temp\\PBMotionControl'
if(Test-Path "$root\\request.py"){throw 'Previous request queued'}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
foreach($n in @('request_done.txt','request_error.txt')){if(Test-Path "$root\\$n"){Move-Item "$root\\$n" "$root\\${stamp}_$n"}}
Copy-Item 'SOURCE' "$root\\request.tmp"
Move-Item "$root\\request.tmp" "$root\\request.py"
'Queued'
""".replace('SOURCE',win)
r=subprocess.run(['python3',str(P/'outputs/video_4k60_20261005_1928/control/vm.py')],input=ps,text=True);r.check_returncode()
