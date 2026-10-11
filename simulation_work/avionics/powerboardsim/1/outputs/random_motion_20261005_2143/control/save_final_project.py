import System
assert System.IO.File.Exists(pbmotionroot+r'\control\MODAL_RENDER_COMPLETE.txt')
assert System.IO.File.Exists(pbmotionroot+r'\videos\random_fig18_pcb_stress\RENDERED.txt')
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
r=ExtAPI.DataModel.GetObjectById(4207);r.Activate()
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.DeformationScaleMultiplier=1
p=pref.GetType().GetProperty('DeformationScaling');p.SetValue(pref,System.Enum.Parse(p.PropertyType,'Auto'),None)
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso);ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync("import System\nSave(Overwrite=True)\nSystem.IO.File.WriteAllText(r'C:\\Temp\\PBMotionControl\\FINAL_VIDEOS_PROJECT_SAVED.txt',System.DateTime.UtcNow.ToString('o'))")
