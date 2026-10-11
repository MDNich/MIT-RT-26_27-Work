JOBS=[{'name': 'random_fig15_pcb_baseX', 'result': 4589, 'local': 'C:\\Temp\\PBMotionVideos\\random_fig15_pcb_baseX', 'host': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\videos\\random_fig15_pcb_baseX'}, {'name': 'random_fig17_pcb_baseZ', 'result': 4605, 'local': 'C:\\Temp\\PBMotionVideos\\random_fig17_pcb_baseZ', 'host': 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\videos\\random_fig17_pcb_baseZ'}]
import System,math
from Ansys.Core.Units import Quantity
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 G=ExtAPI.Graphics
 for j in JOBS:
  out=j['local'];raw=list(System.IO.File.ReadAllLines(out+r'\frame_audit.csv'));rows=[x.split(',') for x in raw[1:]]
  assert len(rows)==480
  bad=[i for i,v in enumerate(rows) if int(v[1])!=i+1 or abs(float(v[2])-(1+(i+1)/16384.))>1e-10]
  System.IO.File.WriteAllLines(out+r'\frame_audit_before_repair.csv',raw)
  if bad:
   r=ExtAPI.DataModel.GetObjectById(j['result']);r.CalculateTimeHistory=False
   p=r.GetType().GetProperty('By');p.SetValue(r,System.Enum.Parse(p.PropertyType,'ResultSet'),None)
   r.SetNumber=1;r.EvaluateAllResults();r.Activate();assert abs(r.Time.Value-(1+1/16384.))<1e-10
   pref=G.ViewOptions.ResultPreference;p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
   pref.ShowMaximum=False;pref.ShowMinimum=False
   G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False;G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
   if j['name']=='random_fig15_pcb_baseX':
    G.Camera.FocalPoint=Ansys.Mechanical.Graphics.Point([34.684950456373,60.391907207066,-0.207545264175],'mm')
    G.Camera.SceneHeight=Quantity(183.01984314377336,'mm')
   else:
    G.Camera.FocalPoint=Ansys.Mechanical.Graphics.Point([34.601610307725,60.351621034801,-1.010433066995],'mm')
    G.Camera.SceneHeight=Quantity(183.96241241456332,'mm')
   bound=float(System.IO.File.ReadAllText(out+r'\legend_bound_m.txt'))
   settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
   def legend_restore():
    legend=Ansys.Mechanical.Graphics.Tools.CurrentLegendSettings();legend.NumberOfBands=10
    for b in range(10):
     legend.SetLowerBound(b,Quantity(-bound+2*bound*b/10.,'m'));legend.SetUpperBound(b,Quantity(-bound+2*bound*(b+1)/10.,'m'))
   legend_restore();G.ExportImage(out+r'\repair_frame_0_check.png',GraphicsImageExportFormat.PNG,settings)
   quarantine=out+r'\rejected_frames';System.IO.Directory.CreateDirectory(quarantine)
   for i in bad:
    if System.IO.File.Exists(r'C:\Temp\PBMotionControl\STOP_RENDER.txt'):raise Exception('Repair stop requested')
    number=i+1;r.SetNumber=number;r.EvaluateAllResults();r.Activate()
    assert abs(r.Time.Value-(1+number/16384.))<1e-10,'Result set did not advance'
    legend_restore();name='AnimationFrame%06d.png'%i;path=System.IO.Path.Combine(out,'frames',name)
    if not System.IO.File.Exists(quarantine+'\\'+name):System.IO.File.Copy(path,quarantine+'\\'+name)
    G.ExportImage(path,GraphicsImageExportFormat.PNG,settings)
    rows[i]=[str(i),str(number),'%.17g'%r.Time.Value,'%.17g'%r.Maximum.Value,'%.17g'%r.Minimum.Value]
   System.IO.File.WriteAllLines(out+r'\frame_audit.csv',[raw[0]]+[','.join(v) for v in rows])
  System.IO.File.WriteAllText(out+r'\REPAIR_AUDIT.txt',repr(bad))
  System.IO.File.WriteAllText(j['host']+r'\REPAIRED.txt',repr(bad))
 System.IO.File.WriteAllText(pbmotionroot+r'\control\REPAIR_XZ_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
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
 import pcb_stress_motion as sm
 a=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+r'\expand_X\IMPORTED.txt')))
 r=a.Solution.AddPythonResult();r.Name='Instantaneous PCB dynamic von Mises - base X'
 System.IO.File.WriteAllText(pbmotionroot+r'\control\STRESS_RESULT_ID.txt',str(r.ObjectId))
 System.IO.File.WriteAllText(pbmotionroot+r'\control\python_result_defaults.txt',r.Text)
 System.IO.File.WriteAllLines(pbmotionroot+r'\control\python_result_methods.txt',[str(x) for x in r.GetType().GetMethods()])
 sel=ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities);sel.Ids=[42342];r.Location=sel
 r.Text="def post_started(sender, analysis):\n    define_dpf_workflow(analysis)\ndef define_dpf_workflow(analysis):\n    import sys\n    cp = "+repr(cp)+"\n    if cp not in sys.path: sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_stress_motion as sm\n    sm.workflow(this)\n"
 r.Connect()
 out=r'C:\Temp\PBMotionStressPilot';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference
 p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'True'),None);pref.DeformationScaleMultiplier=50
 G.ViewOptions.ShowMesh=False;G.ViewOptions.ShowLogo=False;G.ViewOptions.ShowRuler=False
 G.GlobalLegendSettings.ShowDateAndTime=False;G.GlobalLegendSettings.ShowMinMax=False
 pref.ShowMaximum=False;pref.ShowMinimum=False
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 for number in [1,4,120,480]:
  System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\stress_frame.txt',str(number));r.ClearGeneratedData();r.EvaluateAllResults();r.Activate()
  if number==1:
   G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
  G.ExportImage(out+r'\stress_%03d.png'%number,GraphicsImageExportFormat.PNG,settings)
  audit=System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\stress_last.txt');assert eval(audit)['frame']==number;rows.append(audit);System.IO.File.WriteAllLines(pbmotionroot+r'\control\stress_gui_pilot_audit.txt',rows)
 System.IO.File.WriteAllText(pbmotionroot+r'\control\STRESS_PILOT_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
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
