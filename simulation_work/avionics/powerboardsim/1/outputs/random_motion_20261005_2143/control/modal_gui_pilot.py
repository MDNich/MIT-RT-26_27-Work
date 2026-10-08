import System,sys
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 cp=pbmotionroot+r'\control'
 if cp not in sys.path:sys.path.append(cp)
 import mech_dpf
 mech_dpf.setExtAPI(ExtAPI)
 import pcb_modal_motion as sm
 a=ExtAPI.DataModel.GetObjectById(1656)
 r=a.Solution.AddPythonResult();r.Name='Bolted mode 20 - normalized phase animation'
 System.IO.File.WriteAllText(pbmotionroot+r'\control\MODAL_RESULT_ID.txt',str(r.ObjectId))
 System.IO.File.WriteAllText(pbmotionroot+r'\control\modal_python_result_defaults.txt',r.Text)
 System.IO.File.WriteAllLines(pbmotionroot+r'\control\modal_python_result_methods.txt',[str(x) for x in r.GetType().GetMethods()])
 r.Location=ExtAPI.DataModel.GetObjectById(4207).Location
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_modal_motion as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionModalPilot';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=0.003/7.160033972903191
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
 G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 pref.ShowMaximum=False;pref.ShowMinimum=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 for number in [0,45,135]:
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\modal_frame.txt',str(number));r.ClearGeneratedData();r.EvaluateAllResults();r.Activate()
  if number==0:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  G.ExportImage(out+r'\modal_%03d.png'%number,GraphicsImageExportFormat.PNG,settings)
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\modal_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\modal_gui_pilot_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\MODAL_PILOT_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:
 ExtAPI.Application.LicensePreference.DeActivateLicense()
