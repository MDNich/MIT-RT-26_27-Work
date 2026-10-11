# Read-only Mechanical geometry and contact inspection. IronPython compatible.
import System
import traceback
out = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\mounting_faces_live.txt'
f = System.IO.StreamWriter(out, False)
def log(x):
    f.WriteLine(str(x)); f.Flush()
try:
    model = ExtAPI.DataModel.Project.Model
    log('Project: '+str(ExtAPI.DataModel.Project))
    for a in model.Analyses:
        log('Analysis: '+str(a.ObjectId)+' '+a.Name+' '+str(a.WorkingDir))
    for oid in [1696,1732,1771]:
        c=ExtAPI.DataModel.GetObjectById(oid)
        log('CONTACT '+str(oid)+' '+str(c.Name))
        for p in ['ContactType','ContactFormulation','PinballRegion','PinballRadius','InterfaceTreatment','Suppressed']:
            try: log(p+'='+str(getattr(c,p)))
            except: pass
        log('Source='+str(list(c.SourceLocation.Ids)))
        log('Target='+str(list(c.TargetLocation.Ids)))
    for gid in [20040,23089,20407,23329,20878,23269,20466,23209,20246,23389]:
        b=ExtAPI.DataModel.GeoData.GeoEntityById(gid)
        log('BODY '+str(gid)+' '+str(b.Name))
        for face in b.Faces:
            s='FACE '+str(face.Id)
            for p in ['SurfaceType','Centroid','Area','Normal']:
                try:
                    v=getattr(face,p)
                    try: v=list(v)
                    except: pass
                    s+=' '+p+'='+str(v)
                except: pass
            log(s)
    log('Connections methods='+str([x for x in dir(model.Connections) if 'Contact' in x]))
    log('Project save methods='+str([x for x in dir(ExtAPI.DataModel.Project) if 'Save' in x]))
    log('DONE')
except:
    log(traceback.format_exc())
finally:
    f.Close()
