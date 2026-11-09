from pathlib import Path
import os,subprocess,difflib
root=Path(__file__).resolve().parents[1]; repo=Path(os.environ.get('OR_REPO',root/'../../../ActiveControl_MIT_RktTeam')).resolve();work=Path(os.environ.get('CP_WORK',root/'work'))
out=root/'implementation';out.mkdir(exist_ok=True)
prefix=Path('clone/openrocket-release-24.12.RC.01/core/src/main/java/info/openrocket/core/aerodynamics')
files={'BarrowmanCalculator.java':work/'charts/BarrowmanCalculator.java','barrowman/FinSetCalc.java':work/'transfer/FinSetCalc.java','barrowman/SymmetricComponentCalc.java':work/'transfer/SymmetricComponentCalc.java','barrowman/ChartData.java':work/'charts/ChartData.java','barrowman/ChartModel.java':root/'literature/ChartModel.java'}
changes=[]
for suffix,p in files.items():
    dest=prefix/suffix;src=repo/dest;old=src.read_text() if src.exists() else ''
    changes+=list(difflib.unified_diff(old.splitlines(True),p.read_text().splitlines(True),fromfile='a/'+str(dest) if src.exists() else '/dev/null',tofile='b/'+str(dest)))
patch=out/'supersonic-cp-research.patch';patch.write_text(''.join(changes))
subprocess.run(['git','-C',str(repo),'apply','--check',str(patch)],check=True)
subprocess.run(['jar','--create','--file',str(out/'OpenRocket-MIT-6.6-cp-research-overlay.jar'),'-C',str(work/'transfer/classes'),'.'],check=True)
