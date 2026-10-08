import System
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
try:
 r=ExtAPI.DataModel.GetObjectById(4571);r.Activate();G=ExtAPI.Graphics;G.GlobalLegendSettings.ShowMinMax=False
 s=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();s.Width=3840;s.Height=2160;s.CurrentGraphicsDisplay=False;s.FontMagnification=.85
 G.ExportImage(pbmotionroot+r'\videos\random_fig06_baseX_responseX\legend_verified.png',GraphicsImageExportFormat.PNG,s)
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()
