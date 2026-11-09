"""Build research-only chart overlays from an unmodified 6.6 tree; tabulations come from the pinned PDAS archive."""
from pathlib import Path
import re,zipfile,os,subprocess,shutil
ROOT=Path(__file__).resolve().parents[1]
src=Path(os.environ.get('OR_REPO',ROOT/'../../../ActiveControl_MIT_RktTeam'))/'clone/openrocket'
jar=Path(os.environ.get('OR_JAR',src/'build/libs/OpenRocket-MIT-v6.6.jar'))
work=Path(os.environ.get('CP_WORK',ROOT/'work'))/'charts'
work.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(ROOT/'reference/datcom/datcom.zip') as z:f=z.read('datcom.f').decode('latin1').replace('\r','')
wing=f[f.index('      SUBROUTINE SUPLNG'):];body=f[f.index('      DATA ROUTID/4HSUPB,4HOD'):]; defs={}
def table(f,name):
    raw=re.search(r'^      DATA\s+'+name+r'\s*/([^/]+)/',f.replace('&',' '),re.M|re.I).group(1);out=[]
    for a in raw.split(','):
        n,_,v=a.strip().rpartition('*');out.extend([float(v)]*(int(n) if n else 1))
    return out
def arr(a):return '{'+','.join(str(x) for x in a)+'}'
axes=table(wing,'T13246')
defs['WAX']=[axes[:23],axes[23:31],axes[-6:]]
defs['W']=sum([table(wing,'DUMY'+str(i)) for i in range(1,7)],[]);assert len(defs['W'])==23*8*6
for key in ['G13246','DG3246']:defs[key]=table(wing,key)
for suf,force,cp,ny in [('A',11,9,9),('B',10,7,7)]:
    an=table(body,'T4221'+suf);ax=table(body,'T4218'+suf)
    defs['BN'+suf]=[an[:force],an[force:]];defs['BX'+suf]=[ax[:6],ax[cp:]]
    for key in ['D4221','DL218','DR218']:defs[key+suf]=table(body,key+suf)
    assert len(defs['D4221'+suf])==force*8 and len(defs['DL218'+suf])==len(defs['DR218'+suf])==6*ny
out='package info.openrocket.core.aerodynamics.barrowman;\nfinal class ChartData {\n'
for k,a in defs.items():
    if isinstance(a[0],list):out+='static final double[][] '+k+'={'+','.join(arr(b) for b in a)+'};\n'
    else:out+='static final double[] '+k+'='+arr(a)+';\n'
(work/'ChartData.java').write_text(out+'}\n')
pkg=src/'core/src/main/java/info/openrocket/core/aerodynamics'
s=(pkg/'barrowman/FinSetCalc.java').read_text()
start=s.index('        if (finiteWing != null) {');end=s.index('// Multiple fins with',start)
s=s[:start]+'''        if (finiteWing != null && liveFinSet instanceof TrapezoidFinSet tr) {
            double m=conditions.getMach(), w=ChartModel.envelope(m,conditions.getAOA());
            if(w>0 && tr.getSweep()>=0 && tr.getTipChord()<=tr.getRootChord()){
                double n=ChartModel.slope(m,tr.getRootChord(),tr.getTipChord(),tr.getSpan(),tr.getSweep())*finArea/conditions.getRefArea();
                cna1=(1-w)*cna1+w*n; // retain legacy chordwise CP for this force-law ablation
            }
        }
        '''+s[end:]
(work/'FinSetCalc.java').write_text(s)
s=(pkg/'barrowman/SymmetricComponentCalc.java').read_text().replace('public SymmetricComponentCalc(RocketComponent c) {','''private info.openrocket.core.rocketcomponent.NoseCone chartNose;
    public SymmetricComponentCalc(RocketComponent c, boolean charts) {
        this(c);
        if(charts && c instanceof info.openrocket.core.rocketcomponent.NoseCone n && ChartModel.supports(n)) chartNose=n;
    }
    public SymmetricComponentCalc(RocketComponent c) {''')
a=s.index('cp = new Coordinate(cpCache');b=s.index(';',a)+1
s=s[:a]+'''double N=cnaCache*conditions.getSincAOA()/conditions.getRefArea(), x=cpCache;
            double w=ChartModel.envelope(conditions.getMach(),conditions.getAOA());
            if(chartNose!=null && w>0){
                var tab=ChartModel.nose(chartNose,conditions.getMach());
                double n=tab[0]*frontalArea*conditions.getSincAOA()/conditions.getRefArea();
                x=((1-w)*N*x+w*n*tab[1])/((1-w)*N+w*n); N=(1-w)*N+w*n;
            }
            cp=new Coordinate(x,0,0,N).average(getLiftCP(conditions,warnings));'''+s[b:]
(work/'SymmetricComponentCalc.java').write_text(s)
s=(pkg/'BarrowmanCalculator.java').read_text().replace('calcObj = new FinSetCalc(fins, true);','''calcObj = new FinSetCalc(fins, true);
            } else if (finiteWingFins && comp instanceof info.openrocket.core.rocketcomponent.NoseCone n &&
                !Boolean.getBoolean("study.wingOnly")) {
                calcObj=new info.openrocket.core.aerodynamics.barrowman.SymmetricComponentCalc(n,true);''')
(work/'BarrowmanCalculator.java').write_text(s)
classes=work/'classes';classes.mkdir(exist_ok=True)
subprocess.run(['javac','-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,work.glob('*.java')),str(Path(__file__).with_name('ChartModel.java'))],check=True)
