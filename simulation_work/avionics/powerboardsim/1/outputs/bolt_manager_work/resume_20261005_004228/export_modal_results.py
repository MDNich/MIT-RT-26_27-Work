import System,traceback
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,GraphicsResolutionType,ViewOrientationType
case=PCB670_RUN+'\\'+REPORT_CASE
analysis=ExtAPI.DataModel.GetObjectById(REPORT_ANALYSIS_ID)
# Validate the actual result set before evaluating plots.
reader=analysis.GetResultsData();fs=list(reader.ListTimeFreq)
assert len(fs)==20,unicode(fs)
assert all(f>=1 for f in fs)
System.IO.File.WriteAllText(case+r'\frequencies.csv',u'mode,frequency_hz\n'+u'\n'.join(unicode(i+1)+','+unicode(f) for i,f in enumerate(fs)))
reader.Dispose()
analysis.Solution.EvaluateAllResults()
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Width=1800;settings.Height=1200;settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
log=[]
for res in list(analysis.Solution.Children):
 if unicode(res.DataModelObjectCategory)!='TotalDeformation':continue
 res.Activate()
 pref=ExtAPI.Graphics.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling')
 v=[x for x in System.Enum.GetNames(p.PropertyType) if 'auto' in x.lower()][0]
 p.SetValue(pref,System.Enum.Parse(p.PropertyType,v),None)
 p=pref.GetType().GetProperty('ExtraModelDisplay')
 choices=[x for x in System.Enum.GetNames(p.PropertyType) if x.lower() in ['nowireframe','none','noedges']]
 if choices:p.SetValue(pref,System.Enum.Parse(p.PropertyType,choices[0]),None)
 pref.ShowMinimum=False
 ExtAPI.Graphics.ViewOptions.ShowMesh=False
 ExtAPI.Graphics.Camera.SetFit()
 name='mode_%02d.png'%res.Mode
 ExtAPI.Graphics.ExportImage(case+'\\'+name,GraphicsImageExportFormat.PNG,settings)
 log.append(unicode(res.Mode)+' '+unicode(res.Maximum)+' '+unicode(res.Minimum))
 if res.Mode in [1,4]:
  ExtAPI.Graphics.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1)
  ExtAPI.Graphics.Camera.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1)
  ExtAPI.Graphics.Camera.SetFit()
  ExtAPI.Graphics.ExportImage(case+'\\'+'mode_%02d_battery_view.png'%res.Mode,GraphicsImageExportFormat.PNG,settings)
  ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
System.IO.File.WriteAllText(case+r'\image_export.txt',u'\n'.join(log))
# Preserve the solve files before enabling the special bolts.
for name in ['ds.dat','solve.out','file.rst','file0.err','file.aapresults']:
 p=System.IO.Path.Combine(analysis.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,System.IO.Path.Combine(case,name),True)
System.IO.File.WriteAllText(case+r'\RESULTS_VERIFIED.txt','20 real undamped frequencies, minimum search 1 Hz. Native solver output and result file retained.')
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
