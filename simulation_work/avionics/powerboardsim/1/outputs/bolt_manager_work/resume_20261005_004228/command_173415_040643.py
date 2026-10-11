from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
for b in Model.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
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
