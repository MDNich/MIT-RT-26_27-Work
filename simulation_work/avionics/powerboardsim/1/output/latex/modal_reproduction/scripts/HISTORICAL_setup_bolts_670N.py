# Mechanical 2026 R1 / IronPython 2.7. No json; no Solve or contact-tool calls.
# Sets up existing APDL Bolt Manager and exports static input for independent preflight.
import System
import traceback
from Ansys.Mechanical.DataModel.Enums import CoordinateSystemAlignmentType
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
ROOT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1'
WORK=ROOT+r'\outputs\bolt_manager_work'
STAMP=System.DateTime.UtcNow.ToString('yyyyMMdd_HHmmssfff')
OUT=WORK+r'\setup_'+STAMP
System.IO.Directory.CreateDirectory(OUT)
w=System.IO.StreamWriter(OUT+r'\setup_log.txt',False,System.Text.UTF8Encoding(False));w.AutoFlush=True
created=[]; suppressed=[]; initial=None; old_prestress=None
BOLTS=[
 ('01','Left high Y',21279,[21214,21273],range(41970,41978),10.81234895,102.90699896),
 ('02','Center high Y',21629,[21564,21623],range(41962,41970),34.81234887,102.90699896),
 ('03','Right high Y',21979,[21914,21973],range(41954,41962),58.81234883,102.90699896),
 ('04','Left low Y',22329,[22264,22323],range(41914,41922),10.81234894,17.90699886),
 ('05','Center low Y',22679,[22614,22673],range(41922,41930),34.81234886,17.90699886),
 ('06','Right low Y',23029,[22964,23023],range(41930,41938),58.81234882,17.90699886)]
BATTERIES=set([20157,20675,20822]); NICKEL=set([20091,20297,20348,20642,20756,20929])
PCB=42342

def log(s):w.WriteLine(unicode(s))
def write(path,s):System.IO.File.WriteAllText(path,unicode(s),System.Text.UTF8Encoding(False))
def walk(o):
    for c in getattr(o,'Children',[]):
        yield c
        for d in walk(c):yield d

def cat(o):return unicode(getattr(o,'DataModelObjectCategory',''))
def sel(ids):
    s=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    s.Ids=list(ids)
    return s

def scope(location):
    if hasattr(location,'Location'):location=location.Location
    return list(location.Ids)

def tracked(o):created.append(o);return o

def ns(name,ids):
    n=tracked(model.AddNamedSelection());n.Name=name;n.Location=sel(ids);n.SendToSolver=True
    # Explicitly request node components, using the installed enum's actual member.
    p=n.GetType().GetProperty('SendAs')
    et=p.PropertyType
    names=list(System.Enum.GetNames(et))
    opts=[x for x in names if x.lower() in ['nodes','node']]
    if len(opts)!=1:raise Exception('Cannot identify node SendAs enum: '+unicode(names))
    n.SendAs=System.Enum.Parse(et,opts[0])
    log('NS '+name+' '+unicode(scope(n.Location))+' SendAs='+unicode(n.SendAs))
    return n

try:
    log('SETUP ONLY. Six existing solid bolts; 670 N EACH; load then lock. NO SOLVE.')
    model=ExtAPI.DataModel.Project.Model
    objs=list(walk(model))
    if any(unicode(o.Name).startswith('PCB670_') for o in objs):raise Exception('PCB670 setup already exists; refusing duplicates.')
    modal=[a for a in model.Analyses if unicode(a.AnalysisType)=='Modal']
    if len(modal)!=1:raise Exception('Expected exactly one modal analysis.')
    modal=modal[0]
    if ROOT.lower() not in unicode(modal.WorkingDir).lower():raise Exception('Unexpected project path.')
    bodies={b.GetGeoBody().Id:b for b in objs if cat(b)=='Body'}
    if not BATTERIES.union(NICKEL).union([PCB]).issubset(set(bodies)):raise Exception('Required bodies missing.')
    for gid in BATTERIES:
        if unicode(bodies[gid].Material)!='PilesLiPo':raise Exception('Battery material mismatch.')
    for gid in NICKEL:
        if unicode(bodies[gid].Material)!='NICKEL-200':raise Exception('Nickel strip material mismatch.')
    owners={}
    for gid,b in bodies.items():
        owners[gid]=gid
        for f in b.GetGeoBody().Faces:owners[f.Id]=gid
    mesh=ExtAPI.DataModel.MeshDataByName('Global')
    log('Current mesh unit: '+unicode(mesh.Unit))
    for num,label,gid,shaft,hole,x,y in BOLTS:
        if gid not in bodies or bodies[gid].Suppressed:raise Exception('Bolt missing/suppressed: '+num)
        if unicode(bodies[gid].StiffnessBehavior)!='Flexible':raise Exception('Bolt must be flexible for preload: '+num)
        for fid in shaft:
            if owners.get(fid)!=gid:raise Exception('Shaft face owner mismatch: '+num)
        for fid in hole:
            if owners.get(fid)!=PCB:raise Exception('PCB hole face owner mismatch: '+num)
        for fid in [gid]+list(shaft)+list(hole):
            if len(list(mesh.MeshRegionById(fid).NodeIds))==0:raise Exception('Empty mesh scope '+unicode(fid))
        log('VALIDATED bolt '+num+' '+label+' body '+unicode(gid)+' '+unicode(bodies[gid].Name))
    ext=[e for e in ExtAPI.ExtensionManager.Extensions if e.Name=='BoltTools'][0]
    mgrs=[o for o in ExtAPI.DataModel.GetUserObjects(ext) if o.Name=='ApdlBoltManager']
    if len(mgrs)!=1:raise Exception('Expected existing APDL Bolt Manager.')
    manager=mgrs[0]
    if list(manager.Children):raise Exception('Manager has existing children; refusing ambiguous duplication.')
    bm=ext.GetModule().ApdlBoltModule
    bm.LoadXmlApdlBolts()
    part='PCB_ExistingBolt_670N.xml'
    if part not in bm.ApdlBoltDict or bm.ApdlBoltDict[part].LoadErrors:raise Exception('Custom bolt part failed to load.')
    fixed=[o for o in modal.Children if cat(o)=='FixedSupport' and not o.Suppressed]
    if len(fixed)!=1:raise Exception('Expected one existing fixed support.')
    fixed_ids=scope(fixed[0].Location)
    initial=[o for o in modal.Children if cat(o)=='InitialCondition'][0]
    old_prestress=initial.PreStressICEnvironment
    if old_prestress is not None:raise Exception('Modal already has a prestress source; refusing replacement.')
    # Contacts cannot remove a connection made by shared mesh nodes.
    bn={gid:set(mesh.MeshRegionById(gid).NodeIds) for gid in bodies if not bodies[gid].Suppressed}
    for bat in BATTERIES:
        for gid,nds in bn.items():
            if gid != bat and gid not in NICKEL and bn[bat].intersection(nds):
                raise Exception('Battery shares nodes with a non-nickel body '+unicode(gid))
    contacts=[c for c in walk(model.Connections) if cat(c)=='ContactRegion']
    battery_keep=[];battery_remove=[]
    for c in contacts:
        if c.Suppressed:continue
        sb=set(owners[f] for f in scope(c.SourceLocation));tb=set(owners[f] for f in scope(c.TargetLocation))
        if not BATTERIES.intersection(sb.union(tb)):continue
        is_nickel=(sb.issubset(BATTERIES) and tb.issubset(NICKEL)) or (tb.issubset(BATTERIES) and sb.issubset(NICKEL))
        log('BATTERY CONTACT '+unicode(c.ObjectId)+' '+unicode(sorted(sb))+' -> '+unicode(sorted(tb))+' '+('KEEP_NICKEL' if is_nickel else 'SUPPRESS'))
        (battery_keep if is_nickel else battery_remove).append(c)
    if len(battery_keep)!=6:raise Exception('Expected six battery-to-nickel contact regions; got '+unicode(len(battery_keep)))
    for src,dest in [(ROOT+r'\powerboardsim_v1_files\dp0\global\MECH\SYS.mechdb',OUT+r'\before_saved_model.mechdb'),(ROOT+r'\powerboardsim_v1.wbpj',OUT+r'\before_project.wbpj')]:
        if System.IO.File.Exists(src):System.IO.File.Copy(src,dest,False)
    log('Last saved project copied. All pre-edit live checks passed.')
    for c in battery_remove:
        suppressed.append(c);c.Suppressed=True
    static=tracked(model.AddStaticStructuralAnalysis());static.Name='PCB670_Bolt preload - load then lock'
    settings=static.AnalysisSettings
    settings.NumberOfSteps=2
    settings.CurrentStepNumber=1;settings.StepEndTime=Quantity('1 [s]')
    settings.CurrentStepNumber=2;settings.StepEndTime=Quantity('2 [s]')
    support=static.AddFixedSupport();support.Name='PCB670_Existing mounting supports';support.Location=sel(fixed_ids)
    static.Solution.AddTotalDeformation()
    static.Solution.AddEquivalentStress()
    for num,label,gid,shaft,hole,x,y in BOLTS:
        prefix='PCB670_'+num
        body_ns=ns(prefix+'_BODY',[gid]);shaft_ns=ns(prefix+'_SHAFT',shaft);hole_ns=ns(prefix+'_HOLE',hole)
        cs=tracked(model.CoordinateSystems.AddCoordinateSystem());cs.Name=prefix+'_Head axis '+label
        cs.OriginDefineBy=CoordinateSystemAlignmentType.Component
        cs.OriginX=Quantity(unicode(x)+' [mm]');cs.OriginY=Quantity(unicode(y)+' [mm]')
        cs.OriginZ=Quantity('-3.772678375 [mm]')
        obj=manager.CreateChild('ApdlBolt')
        mech=obj.Controller.GetMechanicalObj();tracked(mech)
        mech.Name=prefix+' '+label+' - 670 N then lock'
        obj.Properties['Display/Visible'].Value='No'
        for p in ['Parts/BoltWasherName','Parts/NutName','Parts/NutWasherName']:obj.Properties[p].Value='None'
        obj.Properties['Parts/BoltName'].Value=part
        obj.Attributes['CsIds']=[cs.ObjectId]
        obj.Properties['CS/CsIds'].Value='1 CS'
        text="PBIndex="+unicode(int(num))+"\nPBBody='"+body_ns.SolverName+"'\nPBShaft='"+shaft_ns.SolverName+"'\nPBHole='"+hole_ns.SolverName+"'"
        obj.Attributes['UserCmds']=[['Existing solid bolt scopes',text,['Pre','Solve'],['Bolt'],['Assembly']]]
        obj.Controller.GetData(obj,False)
        obj.NotifyChange()
        log('CREATED APDL BOLT '+unicode(mech.ObjectId)+' '+unicode(mech.Name))
    initial.PreStressICEnvironment=static
    if initial.PreStressICEnvironment.ObjectId!=static.ObjectId:raise Exception('Prestress link not established.')
    log('PRESTRESS LINK to static '+unicode(static.ObjectId))
    log('BATTERY CONTACTS: '+unicode(len(battery_keep))+' to nickel only; '+unicode(len(suppressed))+' other contacts suppressed.')
    ExtAPI.DataModel.Tree.Refresh()
    target=OUT+r'\static_input.dat'
    log('Exporting input only: '+target)
    bm.StartApdlInputFileWrite(static)
    static.WriteInputFile(target)
    if not System.IO.File.Exists(target):raise Exception('No static input exported.')
    data=System.IO.File.ReadAllText(target)
    for s in ['PCB_ExistingBolt_670N.xml','PCB_BOLT_','PBLoad=670']:
        if s not in data.replace(' ','').replace('\t',''):raise Exception('Missing expected native input marker '+s)
    write(OUT+r'\SETUP_CREATED.txt','Six APDL Bolt Manager definitions, 670 N each, load then lock; modal linked. Six nickel-only battery contacts. Input exported, not solved.\n')
    write(WORK+r'\latest_setup.txt',OUT)
    log('SETUP_CREATED. Native no-SOLVE validation still required. No solver launched.')
    manager.Activate()
    print('Six 670 N bolts created and modal linked. No solve started. Input ready for verification.')
except:
    log('ERROR\n'+traceback.format_exc())
    if created:
        try:
            if initial is not None:initial.PreStressICEnvironment=old_prestress
        except:log('Could not restore prestress link: '+traceback.format_exc())
        for o in reversed(created):
            try:o.Delete()
            except:log('Rollback failed for '+unicode(o.Name)+': '+traceback.format_exc())
        for c in suppressed:
            try:c.Suppressed=False
            except:log('Could not restore contact '+unicode(c.ObjectId))
        try:ExtAPI.DataModel.Tree.Refresh()
        except:pass
    print('Setup stopped; see '+OUT+r'\setup_log.txt')
    raise
finally:w.Close()
