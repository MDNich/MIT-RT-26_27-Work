# Read-only API inspection. Does not change the model or start a solver.
import System
import traceback
OUT = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\bolt_manager_work\live_api.txt'
w=System.IO.StreamWriter(OUT,False,System.Text.UTF8Encoding(False));w.AutoFlush=True
def log(x): w.WriteLine(unicode(x))
def show(label,obj):
    log('\n'+label+': '+unicode(type(obj)))
    log(', '.join(dir(obj)))
    try:
        for m in obj.GetType().GetMethods():
            if any(s in m.Name for s in ['Child','User','Stress','Analysis','Module','Extension']):log(m.ToString())
    except: pass
try:
    model=ExtAPI.DataModel.Project.Model
    show('DATAMODEL',ExtAPI.DataModel)
    show('MODEL',model)
    for ext in ExtAPI.ExtensionManager.Extensions:
        log('EXT '+unicode(ext.Name)+' '+unicode(ext.UniqueId))
        if ext.Name == 'BoltTools':
            show('EXTENSION',ext)
            try:
                for obj in ExtAPI.DataModel.GetUserObjects(ext):
                    log('USER '+unicode(obj.Name)+' '+unicode(obj.Caption)+' '+unicode(obj.Id))
                    show('USER OBJECT',obj)
                    show('CONTROLLER',obj.Controller)
                    if hasattr(obj.Controller,'AnsysObj'): show('CONTROLLER ANSYSOBJ',obj.Controller.AnsysObj)
            except: log(traceback.format_exc())
    for a in model.Analyses:
        log('ANALYSIS '+unicode(a.Name)+' '+unicode(a.AnalysisType))
        for c in a.Children:
            if 'stress' in unicode(type(c)).lower():show('PRESTRESS',c)
    log('READ_ONLY_COMPLETE')
except:log(traceback.format_exc())
finally:w.Close()
print('Bolt API inspection written; model unchanged.')
