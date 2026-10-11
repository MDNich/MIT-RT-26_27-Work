import System,sys,mech_dpf,clr,math
import Ans.DataProcessing as dpf
from Ansys.Core.Units import Quantity
mech_dpf.setExtAPI(ExtAPI)
ExtAPI.Application.LicensePreference.DeActivateLicense()
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
try:
 cp=pbmotionroot+r'\control'
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(cp+r'\MODAL_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    import sys\n    cp="+repr(cp)+"\n    if cp not in sys.path:sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_modal_motion_fast as sm\n    sm.workflow(this)\n"
 r.Connect();r.ClearGeneratedData();r.EvaluateAllResults();r.Activate()
 wf=dpf.Workflow(r.WorkflowId)
 System.IO.File.WriteAllText(cp+r'\fast_workflow.txt',str(r.WorkflowId)+'\n'+str(wf))
 System.IO.File.WriteAllLines(cp+r'\workflow_methods.txt',[str(m) for m in clr.GetClrType(dpf.Workflow).GetMethods()])
 out=r'C:\Temp\PBMotionFastModalPilot';System.IO.Directory.CreateDirectory(out)
 G=ExtAPI.Graphics;pref=G.ViewOptions.ResultPreference;pref.DeformationScaleMultiplier=3./7.160033972903191
 G.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);G.Camera.SetFit();G.Camera.SceneHeight=Quantity(G.Camera.SceneHeight.Value*1.3,'mm')
 settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings();settings.Width=3840;settings.Height=2160;settings.CurrentGraphicsDisplay=False;settings.FontMagnification=.85
 rows=[]
 for n in [0,45,135]:
  clock=System.Diagnostics.Stopwatch.StartNew();wf.Connect('phase',System.Double(math.sin(2*math.pi*n/180.)));r.Evaluate();r.Activate();pref.DeformationScaleMultiplier=3./7.160033972903191
  evaltime=clock.Elapsed.TotalSeconds
  G.ExportImage(out+'\\modal_%03d.png'%n,GraphicsImageExportFormat.PNG,settings)
  rows.append(repr({'frame':n,'eval_s':evaltime,'total_s':clock.Elapsed.TotalSeconds}));System.IO.File.WriteAllLines(cp+r'\fast_modal_pilot_audit.txt',rows)
 System.IO.File.WriteAllText(cp+r'\FAST_MODAL_PILOT_COMPLETE.txt',System.DateTime.UtcNow.ToString('o'))
finally:ExtAPI.Application.LicensePreference.DeActivateLicense()
