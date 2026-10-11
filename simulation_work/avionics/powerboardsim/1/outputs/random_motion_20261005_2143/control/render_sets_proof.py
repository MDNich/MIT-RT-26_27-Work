import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 r=ExtAPI.DataModel.GetObjectById(4567);g=ExtAPI.Graphics
 r.CalculateTimeHistory=False
 p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
 g.ViewOptions.ShowMesh=False;g.ViewOptions.ShowLogo=False;g.GlobalLegendSettings.ShowDateAndTime=False
 pref=g.ViewOptions.ResultPreference;p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
 s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False;s.FontMagnification=.85
 out=pbmotionroot+r'\pilot_expand_nodal\actual_sets';System.IO.Directory.CreateDirectory(out)
 audit=[]
 for i in range(1,5):
  r.SetNumber=i;r.EvaluateAllResults();r.Activate()
  if i==1:
   g.Camera.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1);g.Camera.UpVector=Ansys.ACT.Math.Vector3D(-.3,1,-1.3);g.Camera.SetFit();g.Camera.SceneHeight=Quantity(g.Camera.SceneHeight.Value*1.3,'mm')
  g.ExportImage(out+r'\frame_%06d.png'%(i-1),GraphicsImageExportFormat.PNG,s)
  audit.append('%d\t%s\t%s\t%s'%(i,unicode(r.DisplayTime),unicode(r.Maximum),unicode(r.ObjectState)))
 System.IO.File.WriteAllText(out+r'\audit.tsv','\n'.join(audit))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()
