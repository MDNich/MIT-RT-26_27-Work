import System,sys
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 cp=pbmotionroot+r'\control'
 if cp not in sys.path:sys.path.append(cp)
 import mech_dpf
 mech_dpf.setExtAPI(ExtAPI)
 import pcb_modal_motion_v2 as sm
 a=ExtAPI.DataModel.GetObjectById(1656)
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\MODAL_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_modal_motion_v2 as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionModalPilotV2';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=0.003/7.160033972903191
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
 G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 pref.ShowMaximum=False;pref.ShowMinimum=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 for number in [0,45,135]:
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\modal_frame.txt',str(number));r.ClearGeneratedData();r.EvaluateAllResults();r.Activate();pref.DeformationScaleMultiplier=0.003/7.160033972903191
  if number==0:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  G.ExportImage(out+r'\modal_%03d.png'%number,GraphicsImageExportFormat.PNG,settings)
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\modal_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\modal_gui_pilot_v2_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\MODAL_PILOT_V2_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()
