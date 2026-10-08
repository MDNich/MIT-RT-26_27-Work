import System,clr,mech_dpf
import Ans.DataProcessing as dpf
mech_dpf.setExtAPI(ExtAPI)
rows=[]
for n in ['STRESS','MODAL']:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+n+'_RESULT_ID.txt')))
 rows.append(n+' '+str(r.ObjectId))
 rows.append(str(r.PropertyProviderText))
 for p in r.Properties:
  try:rows.append(str(p.Name)+' = '+str(p.Value))
  except:pass
 try:rows.append('Custom scale '+str(r.GetCustomPropertyByPath('Result Scaling/Activate Result Scaling').ValueString))
 except:rows.append('No property provider')
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
rows.extend(['Scale setting '+str(pref.DeformationScaling),'Multiplier '+str(pref.DeformationScaleMultiplier)])
rows.extend([str(m) for m in clr.GetClrType(dpf.Workflow).GetMethods() if 'Warp' in str(m) or 'Contour' in str(m)])
System.IO.File.WriteAllLines(pbmotionroot+r'\control\warp_probe.txt',rows)

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

import System,sys
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 cp=pbmotionroot+r'\control'
 if cp not in sys.path:sys.path.append(cp)
 import mech_dpf
 mech_dpf.setExtAPI(ExtAPI)
 import pcb_stress_motion_v2 as sm
 a=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\expand_X\IMPORTED.txt')))
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\STRESS_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_stress_motion_v2 as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionStressPilotV2';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
 G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 pref.ShowMaximum=False;pref.ShowMinimum=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 for number in [1,4,120,480]:
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\stress_frame.txt',str(number));r.ClearGeneratedData();r.EvaluateAllResults();r.Activate();pref.DeformationScaleMultiplier=50
  if number==1:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  G.ExportImage(out+r'\stress_%03d.png'%number,GraphicsImageExportFormat.PNG,settings)
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\stress_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\stress_gui_pilot_v2_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\STRESS_PILOT_V2_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()
