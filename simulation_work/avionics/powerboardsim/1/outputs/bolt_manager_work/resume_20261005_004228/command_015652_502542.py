# Read-only validation/export after the active tightening solve returns.
import System
static=ExtAPI.DataModel.GetObjectById(4123)
bolted=ExtAPI.DataModel.GetObjectById(1656)
case=PCB670_RUN+r'\bolted750_refined'
System.IO.File.WriteAllText(case+r'\post_static_status.txt',unicode(static.Solution.Status)+'\n'+unicode(static.Solution.ObjectState))
assert unicode(static.Solution.ObjectState)=='Solved','Static solution has not converged'
reader=static.GetResultsData();times=list(reader.ListTimeFreq);reader.Dispose()
assert times and abs(times[-1]-2.0)<1e-8,unicode(times)
audit=System.IO.Path.Combine(static.WorkingDir,'bolt_preload_audit.csv')
assert System.IO.File.Exists(audit),'Missing native bolt force audit'
System.IO.File.Copy(audit,case+r'\bolt_preload_audit.csv',True)
rows=[]
for line in System.IO.File.ReadAllLines(audit)[1:]:
 cols=[x.strip() for x in line.split(',')]
 if len(cols)==5:rows.append([float(x) for x in cols])
locked=[row for row in rows if int(row[0])==2]
assert len(locked)==6,unicode(rows)
assert all(abs(abs(row[4])-750)<1.0 for row in locked),unicode(locked)
assert ExtAPI.DataModel.GetObjectById(1659).PreStressICEnvironment.ObjectId==4123
assert not bolted.AnalysisSettings.Damped
assert bolted.AnalysisSettings.MaximumModesToFind==20
assert abs(bolted.AnalysisSettings.SearchRangeMinimum.Value-1)<1e-8
System.IO.File.WriteAllText(case+r'\STATIC_VERIFIED.txt','Final time 2.0; six locked reactions within 1 N of 750 N.\n'+unicode(times)+'\n'+unicode(locked))
modalcase=PCB670_RUN+r'\bolted750_modal'
System.IO.Directory.CreateDirectory(modalcase)
bm.StartApdlInputFileWrite(bolted);bolted.WriteInputFile(modalcase+r'\modal_input.dat')
System.IO.File.WriteAllText(modalcase+r'\EXPORTED.txt',unicode(bolted.Solution.ObjectState)+'\n'+unicode(bolted.WorkingDir))
