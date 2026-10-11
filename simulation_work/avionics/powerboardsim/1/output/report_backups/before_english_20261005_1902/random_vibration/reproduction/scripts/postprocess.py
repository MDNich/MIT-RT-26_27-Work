# Run after a verified random-vibration solve. RV_CASE_AXIS is supplied by caller.
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
axis=RV_CASE_AXIS
a=rvs[['X','Y','Z'].index(axis)]
case=System.IO.Path.Combine(RV_ROOT,axis)
assert unicode(a.Solution.ObjectState)=='Solved'
for result in list(a.Solution.Children):
 if 'acceleration' in unicode(result.Name).lower():result.AccelerationInG=False
a.Solution.EvaluateAllResults()
rows=['case\tresult_id\tname\tcategory\tstate\tminimum\tmaximum\taverage\tscale']
results=[]
for o in list(a.Solution.Children):
 if not hasattr(o,'Maximum'):continue
 rows.append('\t'.join([axis,str(o.ObjectId),unicode(o.Name),unicode(o.DataModelObjectCategory),unicode(o.ObjectState),unicode(o.Minimum),unicode(o.Maximum),unicode(o.Average),unicode(o.ScaleFactor)]))
 results.append(o)
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'result_summary.tsv'),'\n'.join(rows))
assert all(unicode(o.ObjectState)=='Solved' for o in results)
assert all(o.Maximum.Value>=0 and not System.Double.IsNaN(o.Maximum.Value) and not System.Double.IsInfinity(o.Maximum.Value) for o in results)
# Native tables allow independent extrema and hot-spot location checks.
for o in results:
 o.ExportToTextFile(System.IO.Path.Combine(case,'result_%s.txt'%o.ObjectId))
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Width=1800;settings.Height=1200
settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.ViewOptions.ShowMesh=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False
rv_enum(pref,'ExtraModelDisplay','NoWireframe')
# For the PCB choose the largest directional RMS displacement, not a vector sum.
u=[o for o in results if unicode(o.Name).startswith('PCB RMS displacement')]
dominant=max(u,key=lambda o:o.Maximum.Value)
stress=[o for o in results if unicode(o.DataModelObjectCategory)=='EquivalentStressPSD' and list(o.Location.Ids)==[42342]][0]
for result,tag in [(dominant,'pcb_displacement'),(stress,'pcb_equivalent_stress')]:
 result.Activate()
 ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
 ExtAPI.Graphics.Camera.SetFit()
 ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(case,tag+'.png'),GraphicsImageExportFormat.PNG,settings)
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'image_results.txt'),'%s\n%s'%(dominant.ObjectId,stress.ObjectId))
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'RESULTS_VERIFIED.txt'),'%s finite nonnegative result maxima; all result objects solved.'%len(results))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
