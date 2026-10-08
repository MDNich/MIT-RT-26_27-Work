import System
rows=[]
for oid in [1656,4182]:
 a=ExtAPI.DataModel.GetObjectById(oid)
 rd=a.GetResultsData()
 rows.append(str(oid)+' '+unicode(list(rd.ListTimeFreq)))
 rd.Dispose()
System.IO.File.WriteAllLines(System.IO.Path.Combine(PCB670_RUN,'english_frequency_probe.txt'),rows)
