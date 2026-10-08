case=PCB670_RUN+r'\default_refined'
pf=System.IO.File.ReadAllText(case+r'\preflight.out');assert 'NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0' in pf
assert all(o.Suppressed for o in list(manager.Children))
bm.StartApdlInputFileWrite(baseline);baseline.WriteInputFile(case+r'\launch_modal_input.dat')
def norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert norm(System.IO.File.ReadAllText(case+r'\launch_modal_input.dat'))==norm(System.IO.File.ReadAllText(case+r'\modal_input.dat'))
System.IO.File.WriteAllText(case+r'\SOLVE_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
baseline.Solve(True)
System.IO.File.WriteAllText(case+r'\SOLVE_RETURNED.txt',unicode(baseline.Solution.Status)+'\n'+unicode(baseline.Solution.ObjectState))
for name in ['ds.dat','solve.out','file0.err','file.rst','file.aapresults','file.cnm']:
 p=System.IO.Path.Combine(baseline.WorkingDir,name)
 if System.IO.File.Exists(p):System.IO.File.Copy(p,System.IO.Path.Combine(case,name),True)
