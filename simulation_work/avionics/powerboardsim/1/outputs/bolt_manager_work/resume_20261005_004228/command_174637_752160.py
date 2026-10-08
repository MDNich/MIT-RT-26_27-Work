
import System
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType
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
r=ExtAPI.DataModel.GetObjectById(4278)
assert unicode(r.ObjectState)=='Solved'
r.Activate()
ExtAPI.Graphics.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
ExtAPI.Graphics.Camera.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Graphics.ExportImage(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_vibration_20261005_0950\battery_oblique_preview2.png',GraphicsImageExportFormat.PNG,settings)
