case=PCB670_RUN+r'\bolted750_asymmetric'
pf=System.IO.File.ReadAllText(case+r'\preflight.out');assert 'NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0' in pf
bm.StartApdlInputFileWrite(static);static.WriteInputFile(case+r'\launch_static_input.dat')
def norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert norm(System.IO.File.ReadAllText(case+r'\launch_static_input.dat'))==norm(System.IO.File.ReadAllText(case+r'\static_input.dat'))
System.IO.File.WriteAllText(case+r'\STATIC_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
static.Solve(True)
System.IO.File.WriteAllText(case+r'\STATIC_RETURNED.txt',unicode(static.Solution.Status)+'\n'+unicode(static.Solution.ObjectState))
for name in ['ds.dat','solve.out','file0.err','bolt_preload_audit.csv']:
 p=System.IO.Path.Combine(static.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,System.IO.Path.Combine(case,name),True)
