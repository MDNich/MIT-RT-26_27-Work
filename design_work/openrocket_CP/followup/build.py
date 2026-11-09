"""Change the fin handover in the study overlay; leave forebody and high-Mach weights fixed."""
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
work = Path(os.environ.get('CP_WORK', root/'work')).resolve()
repo = Path(os.environ.get('OR_REPO', root/'../../../ActiveControl_MIT_RktTeam'))
jar = Path(os.environ.get('OR_JAR', repo/'clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar'))
out = work/'handover'
classes = out/'classes'
classes.mkdir(parents=True, exist_ok=True)
source = (work/'transfer/FinSetCalc.java').read_text()
pinned = 'double mix=0.32, n=(1-mix)*cna1+mix*chartN;'
replacement = """// Remain on the chart branch through leading-edge sonic crossing.
                 // Fade to the prior force and first moment with zero endpoint derivatives.
                 double edgeMach = m * tr.getSpan() / Math.hypot(tr.getSweep(), tr.getSpan());
                 double t = Math.max(0, Math.min(1, (edgeMach - 1.15) / 0.15));
                 double handover = t*t*t * (10 + t * (-15 + 6*t));
                 double mix = 1 - (1 - 0.32) * handover;
                 double n = (1 - mix) * cna1 + mix * chartN;"""
assert source.count(pinned) == 1
(out/'FinSetCalc.java').write_text(source.replace(pinned, replacement))
files = [out/'FinSetCalc.java',work/'transfer/SymmetricComponentCalc.java',work/'charts/BarrowmanCalculator.java',
         work/'charts/ChartData.java',root/'literature/ChartModel.java']
subprocess.run(['javac','-cp',str(jar),'-encoding','UTF-8','-d',str(classes),*map(str,files)],check=True)
