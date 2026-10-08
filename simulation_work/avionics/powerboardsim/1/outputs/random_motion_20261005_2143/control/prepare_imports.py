from pathlib import Path
T=Path(__file__).resolve().parents[1]
s=(T/'control/import_X.py').read_text()
for axis in 'YZ':
 v=s.replace("a=ExtAPI.DataModel.GetObjectById(4559)","a=ExtAPI.DataModel.Project.Model.AddTransientStructuralAnalysis()")
 v=v.replace('base X','base '+axis).replace('expand_X','expand_'+axis)
 v=v.replace("System.IO.File.WriteAllText(pbmotionroot", "System.IO.File.WriteAllText(pbmotionroot")
 (T/'control'/('import_'+axis+'.py')).write_text(v)
