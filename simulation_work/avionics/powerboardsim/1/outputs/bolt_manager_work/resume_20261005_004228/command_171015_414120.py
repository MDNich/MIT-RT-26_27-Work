result=ExtAPI.DataModel.GetObjectById(4316)
assert unicode(result.ObjectState)=='Solved'
result.Activate()
for orient,tag in [(ViewOrientationType.Front,'front'),(ViewOrientationType.Back,'back')]:
 ExtAPI.Graphics.Camera.SetSpecificViewOrientation(orient)
 ExtAPI.Graphics.Camera.SetFit()
 ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(RV_ROOT,'Z','assembly_'+tag+'.png'),GraphicsImageExportFormat.PNG,settings)
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'assembly_extra_views.txt'),'Front and Back for result 4316, Z base excitation, global Z response.')
