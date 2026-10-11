import System
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise PrepPost')
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync("import System\nSave(Overwrite=True)\nSystem.IO.File.WriteAllText(r'C:\\Temp\\PBMotionControl\\CHECKPOINT_SAVED.txt',System.DateTime.UtcNow.ToString('o'))")
