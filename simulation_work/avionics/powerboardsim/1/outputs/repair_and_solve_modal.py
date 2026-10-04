# ANSYS Mechanical 2026 R1, embedded IronPython 2.7. Run from Mechanical.
# User authorized contact repair AND one modal solution on 2026-10-04.
# Adds two audited rigid mounting interfaces; forces component -> PCB MPC
# direction to avoid using shared PCB nodes as dependent contact nodes.
# Backs up evidence, checks all contacts, solves ONCE, reports frequencies.
# No json import; all .NET/localized text remains Unicode.
import System
import re
import traceback
from Ansys.Mechanical.DataModel.Enums import (ContactType, ContactFormulation,
    ContactPinballType, ContactInitialEffect, ContactBehavior)
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
from Ansys.Core.Units import Quantity

ROOT = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1'
AUDIT = ROOT + r'\outputs\fresh_connections_20261004_193530757'
STAMP = System.DateTime.UtcNow.ToString('yyyyMMdd_HHmmssfff')
OUT = ROOT + r'\outputs\modal_repair_run_' + STAMP
RUN_MODAL_SOLVE = True  # Explicitly requested by user; only one solve per execution.
System.IO.Directory.CreateDirectory(OUT)
writer = System.IO.StreamWriter(OUT + r'\run_report.txt', False, System.Text.UTF8Encoding(False))
writer.AutoFlush = True

def text(value):
    return u'' if value is None else unicode(value)

def log(message):
    writer.WriteLine(text(message))

def read(path):
    return text(System.IO.File.ReadAllText(path))

def write(path, content):
    System.IO.File.WriteAllText(path, text(content), System.Text.UTF8Encoding(False))

def walk(obj):
    for c in obj.Children:
        yield c
        for d in walk(c):
            yield d

def scope(location):
    if location is None:
        return []
    if not hasattr(location, 'Ids'):
        location = location.Location
    return sorted(int(i) for i in location.Ids)

def joinids(values):
    return u','.join(text(v) for v in sorted(values))

def read_tsv(path):
    lines = read(path).splitlines()
    header = lines[0].split(u'\t')
    return [dict(zip(header,line.split(u'\t'))) for line in lines[1:] if line]

def selection(values):
    s = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    s.Ids = list(values)
    return s

def save_files(source, destination):
    System.IO.Directory.CreateDirectory(destination)
    for path in System.IO.Directory.GetFiles(source):
        System.IO.File.Copy(path, destination + '\\' + System.IO.Path.GetFileName(path), False)

def row_is_connected(status, count):
    # Worksheet fields are localized. Count is authoritative when populated.
    status = text(status).strip().lower()
    if any(w in status for w in [u'inactive',u'inactif',u'inaktiv',u'n/a']):
        return False
    try:
        if int(text(count).strip()) > 0:
            return True
    except:
        pass
    return any(w in status for w in [u'closed',u'sticking',u'ferme',u'ferm\u00e9',u'coll\u00e9',u'geschlossen'])

def parse_frequencies(output):
    marker = 'FREQUENCIES FROM BLOCK LANCZOS ITERATION'
    if marker not in output:
        return []
    block = output.split(marker,1)[1]
    result = []
    for line in block.splitlines():
        m = re.match(r'^\s*(\d+)\s+([-+0-9.eEdD]+)\s*$',line)
        if m:
            mode = int(m.group(1))
            if mode != len(result)+1:
                if result:
                    break
                continue
            result.append(float(m.group(2).replace('D','E').replace('d','e')))
        elif result:
            break
    return result

# End pure helper functions (also tested in the installed IronPython runtime).
created = []
changed = []
contact_tool = None
solve_started = False
committed = False
old_mode_count = None
analysis = None
try:
    model = ExtAPI.DataModel.Project.Model
    candidates = [a for a in model.Analyses if 'powerboardsim_v1_files' in text(a.WorkingDir)
                  and 'Modal' in text(a.AnalysisType)]
    if len(candidates) != 1:
        raise Exception('Expected exactly one Modal analysis in powerboardsim_v1.')
    analysis = candidates[0]
    work = text(analysis.WorkingDir)
    if 'Solving' in text(analysis.ObjectState) or 'Solving' in text(analysis.Solution.ObjectState):
        raise Exception('A solution is already running; no changes made.')
    old_mode_count = analysis.AnalysisSettings.MaximumModesToFind
    log('CONTACT REPAIR AND ONE MODAL SOLVE, UTC ' + STAMP)
    log('ANSYS v261 / Windows 11; existing Mechanical solve configuration: ' + text(analysis.SolveConfiguration))
    log('Working directory: ' + work)
    log('Units: existing model; all new quantities have explicit mm units.')
    log('Physical assumption: battery mounts rigidly clamped/bolted, confirmed by user.')
    log('Existing mesh, supports, material assignments and solve configuration are preserved.')

    # Match CURRENT geometry and scopes to the fresh audit by geometry, not names/IDs of contacts.
    bodies = [b for b in walk(model.Geometry) if text(b.DataModelObjectCategory)=='Body']
    bygeo = dict((int(b.GetGeoBody().Id),b) for b in bodies)
    expected_bodies = read_tsv(AUDIT + r'\bodies.tsv')
    if len(bygeo)!=208 or set(bygeo)!=set(int(b['geo_id']) for b in expected_bodies):
        raise Exception('Body inventory changed since the fresh audit; stopped before edits.')
    owners = {}
    for gid,b in bygeo.items():
        if b.Suppressed:
            raise Exception('Unexpected suppressed body: '+text(b.Name))
        owners[gid]=gid
        for face in b.GetGeoBody().Faces:
            owners[int(face.Id)]=gid
    for b in expected_bodies:
        current=bygeo[int(b['geo_id'])]
        if text(current.Name)!=b['name'] or text(current.Material)!=b['material']:
            raise Exception('Body name or material changed: '+b['name'])
    mesh = ExtAPI.DataModel.MeshDataByName('Global')
    for b in read_tsv(AUDIT+r'\body_mesh_nodes.tsv'):
        actual=set(int(n) for n in mesh.MeshRegionById(int(b['body_geo_id'])).NodeIds)
        expected=set(int(n) for n in b['node_ids'].split(','))
        if actual!=expected:
            raise Exception('Mesh changed since the fresh audit; inspect before applying this repair.')
    contacts=[c for c in walk(model.Connections) if text(c.DataModelObjectCategory)=='ContactRegion']
    def key(c):
        return (joinids(scope(c.SourceLocation)),joinids(scope(c.TargetLocation)))
    byscope={}
    for c in contacts:
        if key(c) in byscope:
            raise Exception('Duplicate contact face scopes already exist.')
        byscope[key(c)]=c
    expected_contacts=read_tsv(AUDIT+r'\contacts.tsv')
    if len(contacts)!=len(expected_contacts):
        raise Exception('Contact count changed since audit; this run is not applied twice.')
    for e in expected_contacts:
        c=byscope.get((e['source_ids'],e['target_ids']))
        if c is None or c.Suppressed or c.ContactType!=ContactType.Bonded or c.ContactFormulation!=ContactFormulation.MPC:
            raise Exception('Contact scopes/type changed since the fresh audit.')
        if text(c.Behavior)!=e['Behavior'] or text(c.PinballRadius)!=e['PinballRadius'] or text(c.InterfaceTreatment)!=e['InterfaceTreatment']:
            raise Exception('Contact settings changed since the fresh audit: '+text(c.Name))
    fixed=[x for x in walk(analysis) if text(x.DataModelObjectCategory)=='FixedSupport' and not x.Suppressed]
    expected_fixed=[23075,23135,23195,23255,23315,23375,23435,23495]
    if len(fixed)!=1 or scope(fixed[0].Location)!=expected_fixed:
        raise Exception('Fixed support changed since audit.')
    components=[]
    for c in contacts:
        sb=set(owners[i] for i in scope(c.SourceLocation))
        tb=set(owners[i] for i in scope(c.TargetLocation))
        if tb==set([42342]) and len(sb)==1 and text(bygeo[list(sb)[0]].Name).startswith('COMP_'):
            components.append(c)
    if len(components)!=172:
        raise Exception('Expected 172 component-to-PCB contacts; found '+text(len(components)))

    # Backup before any model mutation or native contact check.
    save_files(work, OUT+r'\solver_before')
    System.IO.File.Copy(ROOT+r'\powerboardsim_v1_files\dp0\global\MECH\SYS.mechdb',OUT+r'\last_saved_model.mechdb',False)
    log('Previous solver files and last saved database backed up.')
    try:
        backup=OUT+r'\live_model_before.mechdb'
        ExtAPI.DataModel.Project.BackupSaveAsCopy(backup)
        if System.IO.File.Exists(backup):
            log('Live database backup: '+backup)
        else:
            log('Live backup API returned; no single .mechdb file found. Saved database and scope snapshots retained.')
    except:
        log('Live backup API unavailable; saved database and complete audited scopes retained. '+text(traceback.format_exc()))
    before=[]
    for c in contacts:
        before.append(u'\t'.join([text(c.ObjectId),text(c.Name),key(c)[0],key(c)[1],text(c.Behavior)]))
    write(OUT+r'\contacts_before.tsv',u'object_id\tname\tsource\ttarget\tbehavior\n'+u'\n'.join(before))

    # Do not let auto-asymmetric reversal make common PCB nodes dependent
    # on several different components. Source scopes already belong to components.
    for c in components:
        changed.append((c,c.Behavior,c.Name))
        c.Behavior=ContactBehavior.Asymmetric
        if c.Behavior!=ContactBehavior.Asymmetric:
            raise Exception('Asymmetric behavior did not persist: '+text(c.Name))
    log('172 component-to-PCB contacts now explicitly Asymmetric; Bonded/MPC and scopes preserved.')
    mounts=[
        ('Left battery mount - low Y',20466,[20450,20454,20459],23209,[23197]),
        ('Left battery mount - high Y',20246,[20230,20234,20239],23389,[23377])]
    for name,sbody,sfaces,tbody,tfaces in mounts:
        if any(owners.get(f)!=sbody for f in sfaces) or any(owners.get(f)!=tbody for f in tfaces):
            raise Exception('Mounting face ownership mismatch.')
        c=model.Connections.AddContactRegion()
        created.append(c)
        c.SourceLocation=selection(sfaces)
        c.TargetLocation=selection(tfaces)
        c.ContactType=ContactType.Bonded
        c.ContactFormulation=ContactFormulation.MPC
        c.Behavior=ContactBehavior.ProgramControlled
        c.PinballRegion=ContactPinballType.Radius
        c.PinballRadius=Quantity('0.3 [mm]')
        c.InterfaceTreatment=ContactInitialEffect.AdjustToTouch
        c.Suppressed=False
        c.Name=name
        if scope(c.SourceLocation)!=sorted(sfaces) or scope(c.TargetLocation)!=sorted(tfaces):
            raise Exception('Mount scope did not persist.')
        log('ADDED '+name+u': '+text(bygeo[sbody].Name)+u' -> '+text(bygeo[tbody].Name))
    analysis.AnalysisSettings.MaximumModesToFind=20
    contacts=[c for c in walk(model.Connections) if text(c.DataModelObjectCategory)=='ContactRegion' and not c.Suppressed]
    if len(contacts)!=210:
        raise Exception('Expected 210 contacts after repair.')

    # Verify mesh scopes and graph before invoking the native contact check.
    adjacency=dict((gid,set()) for gid in bygeo)
    for c in contacts:
        s=scope(c.SourceLocation);t=scope(c.TargetLocation)
        for side in [s,t]:
            if not side or not any(len(list(mesh.MeshRegionById(f).ElementIds)) for f in side):
                raise Exception('Unmeshed contact scope: '+text(c.Name))
        for a in set(owners[i] for i in s):
            for b in set(owners[i] for i in t):
                adjacency[a].add(b);adjacency[b].add(a)
    reached=set(owners[i] for i in expected_fixed);stack=list(reached)
    while stack:
        for b in adjacency[stack.pop()]-reached:
            reached.add(b);stack.append(b)
    if len(reached)!=208:
        raise Exception('Defined contact graph still has disconnected bodies.')
    def fingerprint():
        return u'\n'.join(sorted(u'|'.join([text(c.ObjectId),key(c)[0],key(c)[1],text(c.ContactType),text(c.ContactFormulation),text(c.Behavior),text(c.PinballRadius),text(c.InterfaceTreatment)]) for c in contacts))
    snapshot=fingerprint()
    write(OUT+r'\contacts_after.txt',snapshot)

    contact_tool=model.Connections.AddContactTool()
    contact_tool.Name='Repair preflight '+STAMP
    worksheet=contact_tool.GetWorksheet()
    worksheet.ScopeToAllContacts()
    worksheet.ActivateAll()
    worksheet.RefreshWorksheet()
    tables=[t for t in contact_tool.Children if hasattr(t,'ExportTextFile')]
    table=tables[0] if tables else contact_tool.AddInitialInformation()
    log('Generating native initial-contact results for all 210 regions.')
    ExtAPI.Log.WriteMessage('Contact repair: checking all 210 contacts before the modal solve.')
    contact_tool.GenerateInitialContactResults()
    table.Activate()
    table.ExportTextFile(OUT+r'\initial_contacts.txt')
    result_rows=list(table.GetWorksheet().GetData())
    contact_by_id=dict((int(c.ObjectId),c) for c in contacts)
    contact_by_name=dict((text(c.Name),int(c.ObjectId)) for c in contacts)
    detected=set();seen=set();raw=[u'contact_object_id\trow_object_id\tvalues']
    for r in result_rows:
        values=[r[i] for i in range(r.Count)]
        oid=int(r.ObjectId)
        if oid not in contact_by_id and values:
            oid=contact_by_name.get(text(values[0]),-1)
        raw.append(text(oid)+u'\t'+text(r.ObjectId)+u'\t'+u' | '.join(text(v) for v in values))
        if oid in contact_by_id:
            seen.add(oid)
            if len(values)>=5 and row_is_connected(values[3],values[4]):
                detected.add(oid)
    write(OUT+r'\initial_contacts_raw.tsv',u'\n'.join(raw))
    missing=set(contact_by_id)-detected
    log('Contact table: '+text(len(result_rows))+' rows; '+text(len(seen))+' regions covered; '+text(len(detected))+' regions connected.')
    if missing:
        log('FAILED OR UNVERIFIED CONTACTS: '+u'; '.join(text(contact_by_id[i].Name) for i in sorted(missing)))
        raise Exception('Native contact check did not verify every contact. Modal solve was not launched.')
    if fingerprint()!=snapshot:
        raise Exception('Contact definitions changed during native preflight.')
    write(OUT+r'\PREFLIGHT_PASSED.txt','All 210 contacts detected; all 208 bodies have a path to fixed support.\n'+snapshot)
    committed=True
    log('PREFLIGHT PASSED: all 210 contacts detected; graph connects all 208 bodies to fixed supports.')

    if not RUN_MODAL_SOLVE:
        log('Preflight only: RUN_MODAL_SOLVE is False.')
    else:
        solve_started=True
        started=System.DateTime.UtcNow
        log('STARTING ONE MODAL SOLVE: 20 modes, existing solve configuration.')
        ExtAPI.Log.WriteMessage('Contact preflight passed. Starting the requested 20-mode modal solve.')
        analysis.Solve(True)
        save_files(work,OUT+r'\solver_after')
        outpath=work+r'\solve.out'
        if not System.IO.File.Exists(outpath) or System.IO.File.GetLastWriteTimeUtc(outpath)<started:
            raise Exception('No new solver output found; old results will not be reported as a new solution.')
        output=read(outpath)
        frequencies=parse_frequencies(output)
        errors=re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*(\d+)',output)
        nearzero=[i+1 for i,f in enumerate(frequencies) if f<=0.001]
        write(OUT+r'\frequencies.tsv',u'mode\tfrequency_hz\n'+u'\n'.join(text(i+1)+u'\t'+text(f) for i,f in enumerate(frequencies)))
        log('New frequencies (Hz): '+u', '.join(text(f) for f in frequencies))
        log('Solution object state: '+text(analysis.Solution.ObjectState))
        log('Solver error count: '+(errors.group(1) if errors else 'UNKNOWN'))
        log('Modes at or below 0.001 Hz: '+joinids(nearzero))
        warningtext=u''
        for p in System.IO.Directory.GetFiles(work,'*.err'):
            warningtext+=read(p)+u'\n'
        write(OUT+r'\solver_warnings.txt',warningtext)
        overlap=any(w in warningtext.lower() for w in ['overconstraint','overlap','multiple constraints','remove certain internal'])
        if len(frequencies)!=20 or errors is None or int(errors.group(1))!=0 or nearzero:
            log('RESULT NEEDS REVIEW: incomplete/error/zero-mode solution. No automatic retry.')
            ExtAPI.Log.WriteWarning('Modal run needs review. Frequencies and warnings saved: '+OUT)
        else:
            log('ALL 20 EXTRACTED MODES ARE ABOVE 0.001 Hz; engineering validity and mesh convergence still require review.')
            if overlap:
                log('MPC/overlap warnings remain; inspect solver_warnings.txt before accepting frequencies.')
            write(OUT+r'\POSITIVE_MODES.txt','20 positive modes extracted. Review warnings and model qualification.\n')
            ExtAPI.Log.WriteMessage('Modal solve finished; 20 positive modes. Report: '+OUT)
    log('DONE. Review report before saving the Workbench project.')
except:
    log('ERROR:\n'+text(traceback.format_exc()))
    if not committed and not solve_started:
        if contact_tool is not None:
            try: contact_tool.Delete()
            except: log('Could not remove diagnostic Contact Tool.')
        for c in reversed(created):
            try: c.Delete()
            except: log('ROLLBACK ERROR deleting added mount: '+text(traceback.format_exc()))
        for c,behavior,name in reversed(changed):
            try:
                c.Behavior=behavior
                c.Name=name
            except: log('ROLLBACK ERROR restoring contact: '+text(traceback.format_exc()))
        if analysis is not None and old_mode_count is not None:
            try: analysis.AnalysisSettings.MaximumModesToFind=old_mode_count
            except: log('ROLLBACK ERROR restoring mode count.')
        log('Preflight/configuration failed: model edits rolled back where possible; no modal solve launched.')
    elif solve_started:
        try:
            failure=OUT+r'\solver_failure'
            if not System.IO.Directory.Exists(failure):save_files(text(analysis.WorkingDir),failure)
        except:log('Could not copy all failure artifacts.')
        log('Solve was attempted once. No automatic restart; repaired model and failure evidence retained.')
    ExtAPI.Log.WriteError('Repair/run stopped. Report: '+OUT+r'\run_report.txt')
finally:
    writer.Close()
