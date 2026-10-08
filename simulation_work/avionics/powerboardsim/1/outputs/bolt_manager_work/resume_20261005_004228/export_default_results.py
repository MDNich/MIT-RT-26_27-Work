import System,traceback
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,GraphicsResolutionType,ViewOrientationType
case=PCB670_RUN+r'\default'
# Validate the actual result set before evaluating plots.
reader=baseline.GetResultsData();fs=list(reader.ListTimeFreq)
assert len(fs)==20,unicode(fs)
assert all(f>=1 for f in fs)
System.IO.File.WriteAllText(case+r'\frequencies.csv',u'mode,frequency_hz\n'+u'\n'.join(unicode(i+1)+','+unicode(f) for i,f in enumerate(fs)))
reader.Dispose()
baseline.Solution.EvaluateAllResults()
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Width=1800;settings.Height=1200;settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
log=[]
for res in list(baseline.Solution.Children):
 if unicode(res.DataModelObjectCategory)!='TotalDeformation':continue
 res.Activate();ExtAPI.Graphics.Camera.SetFit()
 name='mode_%02d.png'%res.Mode
 ExtAPI.Graphics.ExportImage(case+'\\'+name,GraphicsImageExportFormat.PNG,settings)
 log.append(unicode(res.Mode)+' '+unicode(res.Maximum)+' '+unicode(res.Minimum))
System.IO.File.WriteAllText(case+r'\image_export.txt',u'\n'.join(log))
# Preserve the solve files before enabling the special bolts.
for name in ['ds.dat','solve.out','file.rst','file0.err','file.aapresults']:
 p=System.IO.Path.Combine(baseline.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,System.IO.Path.Combine(case,name),True)
System.IO.File.WriteAllText(case+r'\RESULTS_VERIFIED.txt','20 real undamped frequencies, minimum search 1 Hz. Native solver output and result file retained.')
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
