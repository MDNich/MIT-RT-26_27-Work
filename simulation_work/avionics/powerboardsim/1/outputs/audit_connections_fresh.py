# Fresh audit of the CURRENT Mechanical model. ANSYS IronPython 2.7.
# Reads all bodies, contacts, supports and existing mesh. No old IDs are assumed.
# Does not change existing contacts/materials/supports or launch a modal solve.
# Adds a dedicated Contact Tool and attempts initial-contact diagnostics only.
import System
import traceback

ROOT = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1'
STAMP = System.DateTime.UtcNow.ToString('yyyyMMdd_HHmmssfff')
OUT = ROOT + r'\outputs\fresh_connections_' + STAMP
System.IO.Directory.CreateDirectory(OUT)
writers = []

def txt(value):
    if value is None:
        return u''
    return unicode(value)

def cell(value):
    return txt(value).replace(u'\t', u' ').replace(u'\r', u' ').replace(u'\n', u' | ')

def newfile(name, headers=None):
    w = System.IO.StreamWriter(OUT + '\\' + name, False, System.Text.UTF8Encoding(False))
    w.AutoFlush = True
    writers.append(w)
    if headers:
        row(w, headers)
    return w

def row(w, values):
    w.WriteLine(u'\t'.join(cell(v) for v in values))

def get(obj, name, default=u''):
    try:
        return getattr(obj, name)
    except:
        return default

def ids(values):
    return u','.join(txt(v) for v in sorted(values))

def walk(obj):
    for c in get(obj, 'Children', []):
        yield c
        for d in walk(c):
            yield d

def category(obj):
    return txt(get(obj, 'DataModelObjectCategory'))

def props(obj, names):
    return u'; '.join(n + u'=' + txt(get(obj, n)) for n in names)

logfile = newfile('audit_log.txt')
def log(message):
    logfile.WriteLine(txt(message))

# Each operation is isolated so unavailable API properties cannot discard the audit.
try:
    model = ExtAPI.DataModel.Project.Model
    analyses = list(model.Analyses)
    if not any('powerboardsim_v1_files' in txt(get(a, 'WorkingDir')) for a in analyses):
        raise Exception('Expected the open powerboardsim_v1 project; nothing changed.')
    log(u'Fresh CURRENT model audit, UTC ' + STAMP)
    log(u'Existing model definitions are read only. Modal solve is not started.')
    log(u'Geometry coordinates are native GeoData units; mesh coordinates use the mesh unit below.')
    mesh = None
    try:
        mesh = ExtAPI.DataModel.MeshDataByName('Global')
        log(u'Mesh unit: ' + txt(mesh.Unit))
    except:
        log(u'MESH UNAVAILABLE: ' + txt(traceback.format_exc()))
    entities = {}
    owners = {}
    regions = {}
    body_nodes = {}
    body_objects = {}
    allobjects = list(walk(model))
    bodies = [b for b in allobjects if category(b) == 'Body']
    bw = newfile('bodies.tsv', ['object_id','geo_id','name','suppressed','material','stiffness','body_type','centroid_native','mass','volume','node_count','element_count','mesh_error'])
    ew = newfile('entities.tsv', ['body_geo_id','entity_id','kind','surface_type','centroid_native','area_native','node_count','element_count','mesh_error'])
    nw = newfile('body_mesh_nodes.tsv', ['body_geo_id','node_ids'])
    def region(eid):
        if eid in regions:
            return regions[eid]
        if mesh is None:
            result = (set(), set(), u'No mesh data')
        else:
            try:
                r = mesh.MeshRegionById(eid)
                result = (set(r.NodeIds), set(r.ElementIds), u'')
            except:
                result = (set(), set(), u'MeshRegionById unavailable')
        regions[eid] = result
        return result
    for b in bodies:
        try:
            gb = b.GetGeoBody()
            gid = gb.Id
            body_objects[gid] = b
            nodeids, elementids, err = region(gid)
            body_nodes[gid] = nodeids
            row(bw, [b.ObjectId,gid,b.Name,get(b,'Suppressed'),get(b,'Material'),get(b,'StiffnessBehavior'),get(gb,'BodyType'),list(get(gb,'Centroid',[])),get(b,'Mass'),get(b,'Volume'),len(nodeids),len(elementids),err])
            row(nw, [gid,ids(nodeids)])
            for kind, collection in [('Body',[gb]),('Face',get(gb,'Faces',[])),('Edge',get(gb,'Edges',[])),('Vertex',get(gb,'Vertices',[]))]:
                for e in collection:
                    entities[e.Id] = e
                    owners.setdefault(e.Id, set()).add(gid)
                    if kind in ['Body','Face']:
                        ns, es, er = region(e.Id)
                        row(ew,[gid,e.Id,kind,get(e,'SurfaceType'),list(get(e,'Centroid',[])),get(e,'Area'),len(ns),len(es),er])
        except:
            log(u'BODY ERROR object=' + txt(get(b,'ObjectId')) + u' ' + txt(traceback.format_exc()))
    log(u'Bodies exported: ' + txt(len(body_objects)))

    def scope(location):
        # Named selections expose a Location; direct selections expose Ids.
        if location is not None and not hasattr(location, 'Ids'):
            location = get(location, 'Location', None)
        seltype = txt(get(location, 'SelectionType'))
        eids = list(get(location, 'Ids', []))
        bs, ns, es, errors = set(), set(), set(), []
        if 'MeshNodes' in seltype:
            ns.update(eids)
            for gid, bns in body_nodes.items():
                if ns.intersection(bns):
                    bs.add(gid)
        elif 'Geometry' in seltype or (eids and not seltype):
            for eid in eids:
                bs.update(owners.get(eid, set()))
                n, e, err = region(eid)
                ns.update(n); es.update(e)
                if err:
                    errors.append(txt(eid) + u':' + err)
                if eid not in owners:
                    errors.append(txt(eid) + u':unknown geometry owner')
        elif eids:
            errors.append(u'Unresolved selection type ' + seltype)
        return [seltype,ids(eids),ids(bs),len(ns),len(es),u'; '.join(errors)]

    cp = ['ContactType','ContactFormulation','Behavior','PinballRegion','PinballRadius','InterfaceTreatment','ScopingMethod','ContactBodies','TargetBodies']
    cw = newfile('contacts.tsv',['object_id','name','parent','suppressed','state'] + cp + ['source_type','source_ids','source_bodies','source_nodes','source_elements','source_errors','target_type','target_ids','target_bodies','target_nodes','target_elements','target_errors'])
    contacts = [c for c in walk(model.Connections) if category(c) == 'ContactRegion']
    for c in contacts:
        try:
            row(cw,[c.ObjectId,c.Name,get(get(c,'Parent'),'Name'),get(c,'Suppressed'),get(c,'ObjectState')] + [get(c,p) for p in cp] + scope(get(c,'SourceLocation',None)) + scope(get(c,'TargetLocation',None)))
        except:
            log(u'CONTACT ERROR object=' + txt(get(c,'ObjectId')) + u' ' + txt(traceback.format_exc()))
    log(u'Contacts exported: ' + txt(len(contacts)))
    aw = newfile('analysis_objects.tsv',['analysis_id','analysis_name','working_dir','object_id','name','category','suppressed','state','scope_type','scope_ids','scope_bodies','scope_nodes','scope_elements','scope_errors','properties'])
    bcprops = ['DefineBy','Behavior','XComponent','YComponent','ZComponent','RotationX','RotationY','RotationZ','MaximumModesToFind','RangeSearch','MinimumFrequency','MaximumFrequency']
    for a in analyses:
        log(u'Analysis: ' + txt(a.Name) + u'; working directory=' + txt(get(a,'WorkingDir')))
        for obj in [a] + list(walk(a)):
            try:
                row(aw,[a.ObjectId,a.Name,get(a,'WorkingDir'),obj.ObjectId,obj.Name,category(obj),get(obj,'Suppressed'),get(obj,'ObjectState')] + scope(get(obj,'Location',None)) + [props(obj,bcprops)])
            except:
                log(u'ANALYSIS OBJECT ERROR: ' + txt(traceback.format_exc()))
    ow = newfile('other_connections.tsv',['object_id','name','category','suppressed','properties','location','reference','mobile'])
    for c in walk(model.Connections):
        if category(c) != 'ContactRegion':
            row(ow,[get(c,'ObjectId'),get(c,'Name'),category(c),get(c,'Suppressed'),props(c,['Type','JointType','ConnectionType','Behavior','ScopingMethod','ObjectState']),scope(get(c,'Location',None)),scope(get(c,'ReferenceLocation',None)),scope(get(c,'MobileLocation',None))])
    mw = newfile('mesh_controls.tsv',['object_id','name','category','suppressed','properties','scope'])
    for obj in [model.Mesh] + list(walk(model.Mesh)):
        row(mw,[get(obj,'ObjectId'),get(obj,'Name'),category(obj),get(obj,'Suppressed'),props(obj,['ElementOrder','ElementSize','Method','ElementControl','NumberOfDivisions','SweepNumberDivisions','ObjectState']),scope(get(obj,'Location',None))])
    sw = newfile('shared_mesh.tsv',['body_a','body_b','shared_node_count','shared_node_ids'])
    gids = sorted(body_nodes.keys())
    for i in range(len(gids)):
        for j in range(i+1,len(gids)):
            shared = body_nodes[gids[i]].intersection(body_nodes[gids[j]])
            if shared:
                row(sw,[gids[i],gids[j],len(shared),ids(shared)])
    log(u'INVENTORY COMPLETE. Contact definitions alone do not prove active contact.')
    # Retain solver evidence before the contact-only check writes any new files.
    for a in analyses:
        work = txt(get(a,'WorkingDir'))
        if System.IO.Directory.Exists(work):
            backup = OUT + r'\solver_before_' + txt(a.ObjectId)
            System.IO.Directory.CreateDirectory(backup)
            for path in System.IO.Directory.GetFiles(work):
                name = System.IO.Path.GetFileName(path)
                if System.IO.Path.GetExtension(path).lower() in ['.cnm','.out','.err','.dat','.rst','.xml']:
                    try:
                        System.IO.File.Copy(path,backup+'\\'+name,False)
                    except:
                        log(u'Could not copy existing solver file: ' + path)
    try:
        tool = model.Connections.AddContactTool()
        tool.Name = 'Fresh connection audit ' + STAMP
        log(u'Contact Tool default scope: ' + props(tool,['ScopingMethod','Location']))
        tables = [t for t in tool.Children if hasattr(t,'ExportTextFile')]
        table = tables[0] if tables else tool.AddInitialInformation()
        log(u'Generating native initial-contact diagnostics only.')
        tool.GenerateInitialContactResults()
        table.ExportTextFile(OUT + r'\initial_contacts.txt')
        log(u'INITIAL CONTACT TABLE EXPORTED; inspect status and row coverage before concluding connectivity.')
        table.Activate()
    except:
        log(u'INITIAL CONTACT CHECK INCOMPLETE: ' + txt(traceback.format_exc()))
    log(u'DONE. No existing contact, support, material or mesh settings changed; no modal solve started.')
    ExtAPI.Log.WriteMessage('Fresh connection audit saved: ' + OUT)
except:
    log(u'AUDIT ERROR: ' + txt(traceback.format_exc()))
    ExtAPI.Log.WriteError('Fresh audit encountered an error; available data saved: ' + OUT)
finally:
    for w in writers:
        w.Close()
