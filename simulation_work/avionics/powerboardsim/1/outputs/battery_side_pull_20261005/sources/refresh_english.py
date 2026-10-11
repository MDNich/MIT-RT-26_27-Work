import System, Ansys
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory
PULLROOT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\battery_side_pull_20261005'
execfile('Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\bolt_manager_work\\resume_20261005_004228\\bridge.py')
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
Model.Geometry.Name='Geometry'
Model.Geometry.Activate()
ExtAPI.Graphics.ViewOptions.ShowMesh=False
ss=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
ss.Width=2000;ss.Height=1400;ss.Background=GraphicsBackgroundType.White;ss.CurrentGraphicsDisplay=False
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Graphics.ExportImage(PULLROOT+r'\figures\assembly_geometry.png',GraphicsImageExportFormat.PNG,ss)
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=b.GetGeoBody().Id not in [20157,20091,20348,20246,20466,20561,20708,21279,22329]
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Graphics.ExportImage(PULLROOT+r'\figures\edge_battery_cad.png',GraphicsImageExportFormat.PNG,ss)
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
ExtAPI.Graphics.Camera.SetFit()

System.IO.File.WriteAllText(PULLROOT+r'\audit\english_figures_done.txt',System.DateTime.UtcNow.ToString('o'))
ExtAPI.Application.LicensePreference.DeActivateLicense()
