"""Compile the component test overlay using the existing research blend and the pinned PDAS tables."""
from pathlib import Path
import os,re,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
WORK=Path(os.environ.get('CP_WORK',ROOT/'work')).resolve()
OUT=WORK/'afterbody'
REPO=Path(os.environ.get('OR_REPO',ROOT/'../../../ActiveControl_MIT_RktTeam'))
JAR=Path(os.environ.get('OR_JAR',REPO/'clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar'))
OUT.mkdir(parents=True,exist_ok=True)
def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Unexpected baseline: '+old)
    return text.replace(old,new)
with zipfile.ZipFile(ROOT/'reference/datcom/datcom.zip') as archive:
    source=archive.read('datcom.f').decode('latin1').replace('\r','')
routine=source[source.index('      DATA ROUTID/4HSUPB,4HOD'):].replace('&',' ')
def table(key):
    match=re.search(r'^      DATA\s+'+key+r'\s*/([^/]+)/',routine,re.MULTILINE)
    out=[]
    for token in match[1].split(','):
        count,_,value=token.strip().rpartition('*')
        out.extend([float(value)]*(int(count) if count else 1))
    return out
def array(values):return '{'+','.join(map(str,values))+'}'
t={k:table(k) for k in ['T4222A','D4222A','T4222B','D4222B','T4217B','D4217B','D42119']}
t['FLARE_M']=table('DUMY1')+table('DUMY2')
assert len(t['D42119'])==11*7 and len(t['FLARE_M'])==18*11
decl=['static final double[] '+k+'='+array(v)+';' for k,v in t.items()]
for key,src,width in [('TAIL_AXES','T42119',11),('FLARE_AXES','T4220A',18)]:
    a=table(src);decl+=['static final double[][] '+key+'={'+array(a[:width])+','+array(a[width:])+'};']
(OUT/'AfterTables.java').write_text('package info.openrocket.core.aerodynamics.barrowman;\nfinal class AfterTables {\n'+'\n'.join(decl)+'\n}\n')
s=(WORK/'transfer/SymmetricComponentCalc.java').read_text()
s=replace_once(s,'private info.openrocket.core.rocketcomponent.NoseCone chartNose;', '''private info.openrocket.core.rocketcomponent.NoseCone chartNose;
    private BodyPlan.Part bodyPart;
    public SymmetricComponentCalc(RocketComponent c, BodyPlan.Part part) {
        this(c,true);
        this.bodyPart=part;
    }''')
s=replace_once(s,'var tab=ChartModel.nose(chartNose,conditions.getMach());', '''var tab=ChartModel.nose(chartNose,conditions.getMach());
                if(bodyPart!=null && bodyPart.center()!=null){
                    var group=BodyPlan.center(chartNose,bodyPart.center(),conditions.getMach());
                    tab=new double[]{group.slope(),group.station()};
                }''')
s=replace_once(s,'cp=new Coordinate(x,0,0,N).average(getLiftCP(conditions,warnings));','''if(bodyPart!=null && bodyPart.groupedStep())N*=1-w;
            if(bodyPart!=null && bodyPart.terminal() && w>0){
                double weight=ChartModel.envelope(conditions.getMach(),conditions.getAOA());
                var tail=BodyPlan.terminal(2*foreRadius,2*aftRadius,length,conditions.getMach());
                if(tail!=null){
                    weight*=BodyPlan.terminalWeight(2*foreRadius,2*aftRadius,length,conditions.getMach());
                    double trial=tail.slope()*Math.PI*foreRadius*foreRadius*conditions.getSincAOA()/conditions.getRefArea();
                    double sum=(1-weight)*N+weight*trial;
                    x=((1-weight)*N*x+weight*trial*tail.station())/sum; N=sum;
                }
            }
            cp=new Coordinate(x,0,0,N).average(getLiftCP(conditions,warnings));''')
s=replace_once(s,'return new Coordinate(planformCenter, 0, 0, mul * BODY_LIFT_K * planformArea','''double crossflow=BODY_LIFT_K;
        if(bodyPart!=null && bodyPart.crossflow()){
            double weight=ChartModel.envelope(conditions.getMach(),conditions.getAOA());
            crossflow+=weight*(BodyPlan.crossflow(conditions.getMach(),conditions.getAOA())-BODY_LIFT_K);
        }
        return new Coordinate(planformCenter, 0, 0, mul * crossflow * planformArea''')
(OUT/'SymmetricComponentCalc.java').write_text(s)
s=(WORK/'charts/BarrowmanCalculator.java').read_text().replace('checkCache(configuration);','checkBodyConfiguration(configuration);')
s=replace_once(s,'private void buildCalcMap(FlightConfiguration configuration) {','''private boolean[] afterbodyActive;
    private void checkBodyConfiguration(FlightConfiguration cfg) {
        checkCache(cfg);
        if(!finiteWingFins)return;
        int count=cfg.getRocket().getStageCount();
        boolean stale=afterbodyActive==null || afterbodyActive.length!=count;
        if(stale)afterbodyActive=new boolean[count];
        for(int i=0;i<count;i++){
            boolean active=cfg.isStageActive(i);
            if(active!=afterbodyActive[i])stale=true;
            afterbodyActive[i]=active;
        }
        if(stale)voidAerodynamicCache();
    }
    private void buildCalcMap(FlightConfiguration configuration) {
        var bodyParts=info.openrocket.core.aerodynamics.barrowman.BodyPlan.identify(configuration);''')
s=replace_once(s,'} else if (finiteWingFins && comp instanceof info.openrocket.core.rocketcomponent.NoseCone n &&','''} else if(finiteWingFins && bodyParts.containsKey(comp)){
                calcObj=new info.openrocket.core.aerodynamics.barrowman.SymmetricComponentCalc(comp,bodyParts.get(comp));
            } else if (finiteWingFins && comp instanceof info.openrocket.core.rocketcomponent.NoseCone n &&''')
(OUT/'BarrowmanCalculator.java').write_text(s)
classes=OUT/'classes';classes.mkdir(exist_ok=True)
files=[ROOT/'afterbody/BodyPlan.java',OUT/'AfterTables.java',OUT/'BarrowmanCalculator.java',OUT/'SymmetricComponentCalc.java',
       WORK/'transfer/FinSetCalc.java',WORK/'charts/ChartData.java',ROOT/'literature/ChartModel.java']
subprocess.run(['javac','-encoding','UTF-8','-cp',str(JAR),'-d',str(classes),*map(str,files)],check=True)
