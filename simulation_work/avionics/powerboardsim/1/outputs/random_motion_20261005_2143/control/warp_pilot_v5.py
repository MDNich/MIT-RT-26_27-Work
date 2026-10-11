import System,sys
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 cp=pbmotionroot+r'\control'
 if cp not in sys.path:sys.path.append(cp)
 import mech_dpf
 mech_dpf.setExtAPI(ExtAPI)
 import pcb_modal_motion_v5 as sm
 a=ExtAPI.DataModel.GetObjectById(1656)
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\MODAL_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_modal_motion_v5 as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionModalPilotV5';System.IO.Directory.CreateDirectory(out)
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
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\modal_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\modal_gui_pilot_v5_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\MODAL_PILOT_V5_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
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
 import pcb_stress_motion_v5 as sm
 a=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\expand_X\IMPORTED.txt')))
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\control\STRESS_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_stress_motion_v5 as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionStressPilotV5';System.IO.Directory.CreateDirectory(out)
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
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\stress_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\stress_gui_pilot_v5_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\STRESS_PILOT_V5_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()

import System
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 out=r'C:\Temp\PBMotionWarpCompare';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 for mode,native_id,frame,factor in [('stress',4589,1,50),('modal',4207,45,0.003/7.160033972903191)]:
  custom=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+mode.upper()+'_RESULT_ID.txt')))
  System.IO.File.WriteAllText('C:\\Temp\\PBMotionControl\\'+mode+'_frame.txt',str(frame))
  custom.ClearGeneratedData();custom.EvaluateAllResults();custom.Activate();pref.DeformationScaleMultiplier=factor
  G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  height=G.Camera.SceneHeight;focal=G.Camera.FocalPoint
  G.ExportImage(out+'\\'+mode+'_custom.png',GraphicsImageExportFormat.PNG,settings)
  r=ExtAPI.DataModel.GetObjectById(native_id)
  if mode=='stress':r.SetNumber=1;r.EvaluateAllResults()
  r.Activate();pref.DeformationScaleMultiplier=factor
  G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.FocalPoint=focal;G.Camera.SceneHeight=height
  G.ExportImage(out+'\\'+mode+'_native.png',GraphicsImageExportFormat.PNG,settings)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\WARP_COMPARE_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()
