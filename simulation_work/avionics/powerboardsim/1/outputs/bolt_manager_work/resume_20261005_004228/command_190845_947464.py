
import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
OUT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_vibration_20261005_0950\\english_figures_20261005_1902'

for aid,caption in [(1656,'Modal'),(4182,'Modal'),(4254,'Modal'),(4259,'Random Vibration'),(4264,'Random Vibration'),(4269,'Random Vibration')]:
 assert unicode(ExtAPI.DataModel.GetObjectById(aid).SystemCaption)==caption
m=ExtAPI.DataModel.Project.Model
for b in m.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.ViewOptions.ShowMesh=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False;pref.ShowMaximum=True
p=pref.GetType().GetProperty('ExtraModelDisplay')
p.SetValue(pref,System.Enum.Parse(p.PropertyType,'NoWireframe'),None)
rows=['file\tanalysis_id\tresult_id\tname\tstate\tmaximum\tscope_ids\tcamera\tview_vector\tup_vector\tscene_height']
def export_english(filename,aid,oid,angle,width,height,expected):
 a=ExtAPI.DataModel.GetObjectById(aid)
 r=ExtAPI.DataModel.GetObjectById(oid)
 before=r.Maximum.Value
 assert abs(before-expected)<max(abs(expected)*1e-9,1e-12),(oid,before,expected)
 if aid!=4182:assert unicode(a.Solution.ObjectState)=='Solved' and unicode(r.ObjectState)=='Solved'
 r.Activate()
 c=ExtAPI.Graphics.Camera
 if angle=='Battery':
  c.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
  c.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
 elif angle=='ModalBattery':
  c.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1)
  c.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1)
 else:c.SetSpecificViewOrientation(getattr(ViewOrientationType,angle))
 c.SetFit()
 if angle in ['Battery','Back']:c.SceneHeight=Quantity(str(c.SceneHeight.Value*1.25)+' [mm]')
 settings.Width=width;settings.Height=height
 ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(OUT,filename),GraphicsImageExportFormat.PNG,settings)
 assert r.Maximum.Value==before
 rows.append('\t'.join(map(unicode,[filename,aid,oid,r.Name,r.ObjectState,r.Maximum,list(r.Location.Ids),angle,c.ViewVector,c.UpVector,c.SceneHeight])))
 System.IO.File.WriteAllLines(System.IO.Path.Combine(OUT,'export_audit.tsv'),rows)

rows=[x for x in System.IO.File.ReadAllLines(System.IO.Path.Combine(OUT,'export_audit.tsv')) if not x.startswith('AssemblyBack.png\t')]
export_english('AssemblyBack.png',4269,4316,'Back',2100,1400,8.0600162618793547e-5)
