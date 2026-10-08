# Export clean renderings of the already-solved reference, without another solve.
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
ExtAPI.Graphics.ViewOptions.ShowMesh=False
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=1800;settings.Height=1200;settings.Background=GraphicsBackgroundType.White;settings.CurrentGraphicsDisplay=False
for res in list(baseline.Solution.Children):
 if str(res.DataModelObjectCategory)=='TotalDeformation' and res.Mode in [1,4,20]:
  res.Activate();ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);ExtAPI.Graphics.Camera.SetFit()
  ExtAPI.Graphics.ExportImage(PCB670_RUN+r'\default_refined\mode_%02d_clean.png'%res.Mode,GraphicsImageExportFormat.PNG,settings)
  if res.Mode==1:
   ExtAPI.Graphics.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1);ExtAPI.Graphics.Camera.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1);ExtAPI.Graphics.Camera.SetFit()
   ExtAPI.Graphics.ExportImage(PCB670_RUN+r'\default_refined\mode_01_battery_clean.png',GraphicsImageExportFormat.PNG,settings)
