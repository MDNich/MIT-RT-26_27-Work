static=ExtAPI.DataModel.GetObjectById(4123)
bolted=ExtAPI.DataModel.GetObjectById(1656)
case=PCB670_RUN+r'\bolted750_modal'
assert unicode(static.Solution.ObjectState)=='Solved'
assert System.IO.File.Exists(PCB670_RUN+r'\bolted750_refined\STATIC_VERIFIED.txt')
assert System.IO.File.Exists(PCB670_RUN+r'\battery_connection_audit.txt')
pf=System.IO.File.ReadAllText(case+r'\preflight.out')
assert 'NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0' in pf
assert 'PRESTRESS_PARENT_AND_MODAL_GUARDS_VERIFIED' in pf
assert not bolted.AnalysisSettings.Damped
assert bolted.AnalysisSettings.MaximumModesToFind==20
assert bolted.AnalysisSettings.SearchRangeMinimum.Value==1
bm.StartApdlInputFileWrite(bolted);bolted.WriteInputFile(case+r'\launch_modal_input.dat')
def norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert norm(System.IO.File.ReadAllText(case+r'\launch_modal_input.dat'))==norm(System.IO.File.ReadAllText(case+r'\modal_input.dat'))
System.IO.File.WriteAllText(case+r'\MODAL_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
bolted.Solve(True)
System.IO.File.WriteAllText(case+r'\MODAL_RETURNED.txt',unicode(bolted.Solution.Status)+'\n'+unicode(bolted.Solution.ObjectState))
for name in ['ds.dat','solve.out','file0.err','file.rst','file.cnm','file.aapresults','file.cnd']:
 p=System.IO.Path.Combine(bolted.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,System.IO.Path.Combine(case,name),True)
