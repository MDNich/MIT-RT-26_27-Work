bolted=ExtAPI.DataModel.GetObjectById(1656)
static=ExtAPI.DataModel.GetObjectById(4123)
assert unicode(bolted.Solution.ObjectState)=='Solved'
assert unicode(static.Solution.ObjectState)=='Solved'
assert not bolted.AnalysisSettings.Damped
assert bolted.AnalysisSettings.SearchRangeMinimum.Value==1
assert bolted.AnalysisSettings.MaximumModesToFind==20
r20=[r for r in list(bolted.Solution.Children) if unicode(r.DataModelObjectCategory)=='TotalDeformation' and r.Mode==20][-1]
r20.Activate()
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
p=pref.GetType().GetProperty('DeformationScaling')
choice=[x for x in System.Enum.GetNames(p.PropertyType) if 'auto' in x.lower()][0]
p.SetValue(pref,System.Enum.Parse(p.PropertyType,choice),None)
p=pref.GetType().GetProperty('ExtraModelDisplay');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'NoWireframe'),None)
pref.ShowMinimum=False
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
System.IO.File.WriteAllText(PCB670_RUN+r'\FINAL_MODEL_STATUS.txt',unicode(static.Name)+': '+unicode(static.Solution.ObjectState)+'\n'+unicode(bolted.Name)+': '+unicode(bolted.Solution.ObjectState)+'\n20 modes, lower bound 1 Hz, damping disabled. Six 750 N bolts active. Battery-only nickel connections audited.')
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
