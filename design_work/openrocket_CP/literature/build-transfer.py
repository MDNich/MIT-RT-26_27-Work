"""Create the constrained Java implementation; starts from unmodified finite wing and generated chart code."""
from pathlib import Path
import json,os,subprocess
root=Path(__file__).resolve().parents[1];w=Path(os.environ.get('CP_WORK',root/'work'));q=w/'transfer';q.mkdir(exist_ok=True)
src=Path(os.environ.get('OR_REPO',root/'../../../ActiveControl_MIT_RktTeam'))/'clone/openrocket';jar=Path(os.environ.get('OR_JAR',src/'build/libs/OpenRocket-MIT-v6.6.jar'))
pars=json.loads((root/'results/transfer.json').read_text());a,b=pars['a'],pars['b']
p=src/'core/src/main/java/info/openrocket/core/aerodynamics/barrowman/FinSetCalc.java';s=p.read_text();s=s.replace('        if (finiteWing != null) {','        double legacyN=cna1, legacyX=x;\n        if (finiteWing != null) {')
pos=s.index('// Multiple fins with')
s=s[:pos]+'''if(finiteWing!=null && liveFinSet instanceof TrapezoidFinSet tr && tr.getSweep()>=0 && tr.getTipChord()<=tr.getRootChord()){
             double m=conditions.getMach(), w=ChartModel.envelope(m,conditions.getAOA());
             if(w>0){
                 double chartN=(1-w)*legacyN+w*ChartModel.slope(m,tr.getRootChord(),tr.getTipChord(),tr.getSpan(),tr.getSweep())*finArea/conditions.getRefArea();
                 double mix=FIN_FRACTION, n=(1-mix)*cna1+mix*chartN;
                 x=((1-mix)*cna1*x+mix*chartN*legacyX)/n; cna1=n;
             }
         }
         '''.replace('FIN_FRACTION',str(a))+s[pos:];(q/p.name).write_text(s)
p=w/'charts/SymmetricComponentCalc.java';s=p.read_text().replace('double w=ChartModel.envelope','double w='+str(b)+'*ChartModel.envelope');(q/p.name).write_text(s)
classes=q/'classes';classes.mkdir(exist_ok=True)
files=[q/'FinSetCalc.java',q/p.name,w/'charts/BarrowmanCalculator.java',w/'charts/ChartData.java',root/'literature/ChartModel.java']
subprocess.run(['javac','-cp',str(jar),'-encoding','UTF-8','-d',str(classes),*map(str,files)],check=True)
