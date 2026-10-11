# ANSYS Mechanical 2026 R1 / embedded IronPython 2.7.
# For powerboardsim_v1 only. Adds the two missing rigid battery mounting contacts.
# Does not launch a modal solution, change supports, or change material assignments.
# Rerunning reuses the two exact contacts; conflicting scopes stop before mutation.
import System
import traceback
from Ansys.Mechanical.DataModel.Enums import (
    ContactType, ContactFormulation, ContactPinballType, ContactInitialEffect,
    DataModelObjectCategory)
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
from Ansys.Core.Units import Quantity

ROOT = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1'
OUT = ROOT + r'\outputs'
STAMP = System.DateTime.UtcNow.ToString('yyyyMMdd_HHmmssfff')
REPORT = OUT + r'\battery_mount_repair_' + STAMP + '.txt'
CHECKFILE = OUT + r'\battery_mount_initial_contacts_' + STAMP + '.txt'

# Scopes were inspected live using inspect_mounting_faces.py.
# The washer's upper plane and two adjoining inner fillets face the support end.
# Plane separation is approximately 0.1745 mm; pinball is local to these faces.
NEW = [
    ('Battery mount - Part24 to LPattern1_14', 20466, 'Part 24[1]',
     [20450, 20454, 20459], 23209, 'LPattern1[14]', [23197]),
    ('Battery mount - Part26 to Part30', 20246, 'Part 26[1]',
     [20230, 20234, 20239], 23389, 'Part 30[1]', [23377]),
]
EXISTING = [
    (1696, 'Zone de contact 183', [20024, 20028], [23077]),
    (1732, 'Zone de contact 195', [20395, 20400], [23317]),
    (1771, 'Zone de contact 208', [20862, 20866], [23257]),
]
PROPS = ['Name', 'ContactType', 'ContactFormulation', 'PinballRegion',
         'PinballRadius', 'InterfaceTreatment', 'Suppressed']

def descendants(obj):
    for child in obj.Children:
        yield child
        for item in descendants(child):
            yield item

def selection(ids):
    result = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    result.Ids = ids
    return result

def scope_ids(location):
    return list(location.Ids) if location is not None else []

def same_scope(contact, source, target):
    return sorted(scope_ids(contact.SourceLocation)) == sorted(source) and \
        sorted(scope_ids(contact.TargetLocation)) == sorted(target)

def radius_mm(contact):
    q = contact.PinballRadius
    to_mm = {'m': 1000.0, 'mm': 1.0, 'cm': 10.0, 'um': 0.001,
             'in': 25.4, 'ft': 304.8}
    if unicode(q.Unit) not in to_mm:
        raise Exception('Unrecognized pinball unit: ' + unicode(q.Unit))
    return q.Value * to_mm[unicode(q.Unit)]

def configure(contact):
    # Do not rewrite already-correct values: property writes can trigger the
    # automatic, localized contact-name generator in Mechanical.
    settings = [('ContactType', ContactType.Bonded),
                ('ContactFormulation', ContactFormulation.MPC),
                ('PinballRegion', ContactPinballType.Radius),
                ('InterfaceTreatment', ContactInitialEffect.AdjustToTouch),
                ('Suppressed', False)]
    for prop, value in settings:
        if getattr(contact, prop) != value:
            setattr(contact, prop, value)
    if abs(radius_mm(contact) - 0.3) > 1e-8:
        contact.PinballRadius = Quantity('0.3 [mm]')

def verify(contact, source, target):
    if not same_scope(contact, source, target):
        raise Exception('Unexpected face scope: ' + contact.Name)
    if contact.ContactType != ContactType.Bonded or \
       contact.ContactFormulation != ContactFormulation.MPC or \
       contact.PinballRegion != ContactPinballType.Radius or \
       contact.InterfaceTreatment != ContactInitialEffect.AdjustToTouch or contact.Suppressed:
        raise Exception('Contact settings did not persist: ' + contact.Name)
    if abs(radius_mm(contact) - 0.3) > 1e-8:
        raise Exception('Incorrect pinball radius: ' + contact.Name)

writer = System.IO.StreamWriter(REPORT, False)
def log(message):
    # Mechanical supplies Unicode names (for example French "Colle" with an
    # accented e). IronPython str() rejects them; preserve Unicode for .NET.
    writer.WriteLine(unicode(message))
    writer.Flush()

created = []
snapshots = []
committed = False
try:
    model = ExtAPI.DataModel.Project.Model
    log('Battery mounting repair: ' + STAMP + ' UTC')
    log('Assumption: battery mounts are rigidly clamped/bolted, as confirmed by user.')
    log('Modal solve is NOT started by this script.')
    if not any('powerboardsim_v1_files' in str(a.WorkingDir) for a in model.Analyses):
        raise Exception('Wrong project: expected powerboardsim_v1.')
    contacts = [c for c in descendants(model.Connections)
                if c.DataModelObjectCategory == DataModelObjectCategory.ContactRegion]
    planned = []
    for oid, name, source, target in EXISTING:
        # Display names and tree object IDs can change. Exact geometry scopes
        # identify the interface; preserve either existing orientation.
        matches = [c for c in contacts if same_scope(c, source, target) or
                   same_scope(c, target, source)]
        if len(matches) != 1:
            log('EXPECTED ' + name + ' source=' + unicode(source) +
                ' target=' + unicode(target) + ' matches=' + unicode(len(matches)))
            for candidate in contacts:
                cs = scope_ids(candidate.SourceLocation)
                ct = scope_ids(candidate.TargetLocation)
                if set(cs + ct).intersection(source + target):
                    log('CANDIDATE object=' + unicode(candidate.ObjectId) +
                        ' name=' + candidate.Name + ' source=' + unicode(cs) +
                        ' target=' + unicode(ct))
            raise Exception('Expected exactly one contact with the inspected faces: ' + name)
        c = matches[0]
        planned.append((c, scope_ids(c.SourceLocation), scope_ids(c.TargetLocation)))
        log('MATCHED ' + name + ' by faces: object=' + unicode(c.ObjectId) +
            ' current name=' + c.Name)
    new_plans = []
    for name, sbid, sname, source, tbid, tname, target in NEW:
        sb = ExtAPI.DataModel.GeoData.GeoEntityById(sbid)
        tb = ExtAPI.DataModel.GeoData.GeoEntityById(tbid)
        if sb.Name.split('|')[-1] != sname or tb.Name.split('|')[-1] != tname:
            raise Exception('Body identity changed: ' + name)
        sf = set(f.Id for f in sb.Faces)
        tf = set(f.Id for f in tb.Faces)
        if not set(source).issubset(sf) or not set(target).issubset(tf):
            raise Exception('Face ownership changed: ' + name)
        matches = []
        for c in contacts:
            cs = set(scope_ids(c.SourceLocation))
            ct = set(scope_ids(c.TargetLocation))
            sb_scope = sf | set([sbid])
            tb_scope = tf | set([tbid])
            if (cs.intersection(sb_scope) and ct.intersection(tb_scope)) or \
               (cs.intersection(tb_scope) and ct.intersection(sb_scope)):
                matches.append(c)
        if len(matches) > 1:
            raise Exception('Multiple contacts already join this body pair: ' + name)
        if matches:
            c = matches[0]
            if not (same_scope(c, source, target) or same_scope(c, target, source)):
                raise Exception('A differently scoped contact already joins this pair: ' + c.Name)
            planned.append((c, scope_ids(c.SourceLocation), scope_ids(c.TargetLocation)))
            log('Reusing: ' + c.Name)
        else:
            new_plans.append((name, source, target))
    # Preserve saved database in addition to the full project snapshot already made.
    db = ROOT + r'\powerboardsim_v1_files\dp0\global\MECH\SYS.mechdb'
    backup = OUT + r'\before_battery_mounts_' + STAMP + '.mechdb'
    System.IO.File.Copy(db, backup, False)
    log('Saved-database backup: ' + backup)
    log('Saved database backup does not include unsaved edits; old contact values follow.')
    for c, source, target in planned:
        old = [(p, getattr(c, p)) for p in PROPS]
        snapshots.append((c, old))
        log('BEFORE ' + c.Name + ': ' + '; '.join(p + '=' + unicode(v) for p, v in old))
    desired_names = {}
    for name, source, target in new_plans:
        c = model.Connections.AddContactRegion()
        created.append(c)
        c.Name = name
        c.SourceLocation = selection(source)
        c.TargetLocation = selection(target)
        planned.append((c, source, target))
        desired_names[c.ObjectId] = name
    for c, source, target in planned:
        configure(c)
        verify(c, source, target)
        if c.ObjectId in desired_names:
            c.Name = desired_names[c.ObjectId]
        log('VERIFIED object=' + str(c.ObjectId) + ' name=' + c.Name +
            ' source=' + str(source) + ' target=' + str(target) +
            ' Bonded/MPC pinball=0.3 mm')
    committed = True
    log('CONTACT_DEFINITIONS_VERIFIED: ' + str(len(planned)) +
        '; newly created=' + str(len(created)))
    ExtAPI.Log.WriteMessage('Battery mounting contacts configured: ' + str(len(created)) +
                           ' added, five definitions verified. Checking initial contact status.')
    # This is an initial-contact preflight, not an eigenvalue or load-step solve.
    # Keep a dedicated contact tool, and export results for inspection.
    try:
        matches = [c for c in model.Connections.Children
                   if c.Name == 'Battery mounting contact check']
        tool = matches[0] if matches else model.Connections.AddContactTool()
        tool.Name = 'Battery mounting contact check'
        tables = [c for c in tool.Children if hasattr(c, 'ExportTextFile')]
        table = tables[0] if tables else tool.AddInitialInformation()
        tool.GenerateInitialContactResults()
        table.ExportTextFile(CHECKFILE)
        if not System.IO.File.Exists(CHECKFILE) or System.IO.FileInfo(CHECKFILE).Length == 0:
            raise Exception('Contact table export is empty.')
        table.Activate()
        log('INITIAL_CONTACT_TABLE_EXPORTED: ' + CHECKFILE)
        log('The exported table must be inspected; generation alone does not prove every contact is closed.')
        ExtAPI.Log.WriteMessage('Battery mounting contacts added. Initial contact table: ' + CHECKFILE)
    except:
        log('CONTACT_CHECK_INCOMPLETE:\n' + traceback.format_exc())
        ExtAPI.Log.WriteWarning('Contact definitions were applied, but the initial-contact check needs review. See ' + REPORT)
    log('DONE. Save the Workbench project after reviewing the contact table. Modal solution has not been rerun.')
except:
    log('ERROR:\n' + traceback.format_exc())
    if not committed:
        for c in reversed(created):
            try:
                c.Delete()
            except:
                log('ROLLBACK ERROR deleting new contact: ' + traceback.format_exc())
        for c, old in snapshots:
            try:
                # Radius can only be restored while Radius mode is active.
                c.PinballRegion = ContactPinballType.Radius
                for p, v in old:
                    if p not in ['PinballRegion', 'Name']:
                        setattr(c, p, v)
                c.PinballRegion = dict(old)['PinballRegion']
                c.Name = dict(old)['Name']
            except:
                log('ROLLBACK ERROR restoring ' + c.Name + ': ' + traceback.format_exc())
        log('Rollback attempted; inspect any ROLLBACK ERROR above.')
    ExtAPI.Log.WriteError('Battery mounting repair could not finish. Report: ' + REPORT)
    raise
finally:
    writer.Close()
