for a in rvs:assert unicode(a.Solution.ObjectState)=='Solved'
ExtAPI.DataModel.GetObjectById(4316).Activate()
ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
ExtAPI.Graphics.Camera.SetFit()
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'assembly_views_saved.txt'),System.DateTime.UtcNow.ToString('o'))
