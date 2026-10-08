
import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType
OUT=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\battery_oblique_20261005'
m=ExtAPI.DataModel.Project.Model
for b in m.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Width=2100;settings.Height=1400
settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.ViewOptions.ShowMesh=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False;pref.ShowMaximum=True
p=pref.GetType().GetProperty('ExtraModelDisplay')
p.SetValue(pref,System.Enum.Parse(p.PropertyType,'NoWireframe'),None)
rows=['base_axis\tresponse_axis\tanalysis_id\tresult_id\tname\tmaximum\tscale_factor\tlocation_ids\tfile\tscene_height']
for axis,aid,ids in [('X',4259,[4278,4280,4282]),('Y',4264,[4297,4299,4301]),('Z',4269,[4312,4314,4316])]:
 a=ExtAPI.DataModel.GetObjectById(aid)
 assert unicode(a.Solution.ObjectState)=='Solved'
 for comp,oid in zip(['X','Y','Z'],ids):
  result=ExtAPI.DataModel.GetObjectById(oid)
  assert unicode(result.ObjectState)=='Solved'
  assert unicode(result.Name)=='RMS displacement '+comp+' - base '+axis
  before=result.Maximum.Value
  result.Activate()
  camera=ExtAPI.Graphics.Camera
  camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
  camera.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
  camera.SetFit()
  camera.SceneHeight=Quantity(str(camera.SceneHeight.Value*1.25)+' [mm]')
  filename='Base'+axis+'_Response'+comp+'.png'
  ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(OUT,filename),GraphicsImageExportFormat.PNG,settings)
  assert result.Maximum.Value==before
  rows.append('\t'.join(map(unicode,[axis,comp,aid,oid,result.Name,result.Maximum,result.ScaleFactor,list(result.Location.Ids),filename,camera.SceneHeight])))
  System.IO.File.WriteAllText(System.IO.Path.Combine(OUT,'export_audit.tsv'),'\n'.join(rows))
System.IO.File.WriteAllText(System.IO.Path.Combine(OUT,'COMPLETE.txt'),System.DateTime.UtcNow.ToString('o')+'\n9 native exports, unchanged solved result maxima. ViewVector=(1,-1,-1), UpVector=(-0.3,1,-1.3), SetFit then SceneHeight x1.25.')
ExtAPI.DataModel.GetObjectById(4278).Activate()
ExtAPI.Graphics.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
ExtAPI.Graphics.Camera.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Graphics.Camera.SceneHeight=Quantity(str(ExtAPI.Graphics.Camera.SceneHeight.Value*1.25)+' [mm]')
