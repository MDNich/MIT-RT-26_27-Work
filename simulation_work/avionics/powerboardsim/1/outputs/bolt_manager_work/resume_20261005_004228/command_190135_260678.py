import System
m=ExtAPI.DataModel.Project.Model
rows=['culture='+unicode(System.Threading.Thread.CurrentThread.CurrentUICulture)]
for oid in [1656,4182,4254,4259,4264,4269]:
 a=ExtAPI.DataModel.GetObjectById(oid)
 rows.append('ANALYSIS '+unicode(oid)+' '+unicode(a.Name)+' '+unicode(a.Solution.ObjectState))
 if oid in [1656,4182]:
  for r in a.Solution.Children:
   rows.append('RESULT '+unicode(r.ObjectId)+' '+unicode(r.Name)+' '+unicode(r.ObjectState)+' '+unicode(getattr(r,'Mode',''))+' '+unicode(getattr(r,'Maximum','')))
for oid in [4335,4348,4361,4289,4278,4301,4316]:
 r=ExtAPI.DataModel.GetObjectById(oid)
 rows.append('RANDOM '+unicode(oid)+' '+unicode(r.Name)+' '+unicode(r.ObjectState)+' '+unicode(r.Maximum))
System.IO.File.WriteAllLines(System.IO.Path.Combine(PCB670_RUN,'english_probe.txt'),rows)
