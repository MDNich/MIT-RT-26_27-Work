"""Export the independent afterbody overlay and a standalone diff against the pinned MIT source."""
import difflib
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = Path(os.environ.get('OR_REPO',root/'../../../ActiveControl_MIT_RktTeam')).resolve()
work = Path(os.environ.get('CP_WORK', root/'work'))
impl = root/'implementation'
base = '18bbfbd4'
source = Path('clone/openrocket-release-24.12.RC.01/core/src/main/java/info/openrocket/core/aerodynamics')
files = {'BarrowmanCalculator.java': work/'afterbody/BarrowmanCalculator.java',
         'barrowman/FinSetCalc.java': work/'transfer/FinSetCalc.java',
         'barrowman/SymmetricComponentCalc.java': work/'afterbody/SymmetricComponentCalc.java',
         'barrowman/ChartData.java': work/'charts/ChartData.java',
         'barrowman/ChartModel.java': root/'literature/ChartModel.java',
         'barrowman/AfterTables.java': work/'afterbody/AfterTables.java',
         'barrowman/BodyPlan.java': root/'afterbody/BodyPlan.java'}
changes = []
for relative,path in files.items():
    dest = str(source/relative)
    if relative in ('BarrowmanCalculator.java','barrowman/FinSetCalc.java','barrowman/SymmetricComponentCalc.java'):
        original=subprocess.check_output(['git','-C',str(repo),'show',base+':'+dest],text=True)
        name='a/'+dest
    else:
        original=''
        name='/dev/null'
    changes.extend(difflib.unified_diff(original.splitlines(True),path.read_text().splitlines(True),
                                        fromfile=name,tofile='b/'+dest))
patch=impl/'afterbody-research.patch'
patch.write_text(''.join(changes))
subprocess.run(['git','-C',str(repo),'apply','--check',str(patch)],check=True)
subprocess.run(['jar','--create','--date=2026-11-09T00:00:00Z','--file',
                str(impl/'OpenRocket-MIT-6.6-afterbody-overlay.jar'),'-C',str(work/'afterbody/classes'),'.'],check=True)
