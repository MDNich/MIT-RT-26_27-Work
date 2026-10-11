case=PCB670_RUN+r'\default\bounded_10k'
pf=System.IO.File.ReadAllText(case+r'\preflight.out')
assert 'NUMBER OF ERROR   MESSAGES ENCOUNTERED=          0' in pf
assert baseline.AnalysisSettings.SearchRangeMinimum.Value==1 and baseline.AnalysisSettings.SearchRangeMaximum.Value==10000
assert baseline.AnalysisSettings.MaximumModesToFind==20 and not baseline.AnalysisSettings.Damped
assert all(o.Suppressed for o in list(manager.Children))
e.GetModule().ApdlBoltModule.StartApdlInputFileWrite(baseline)
baseline.WriteInputFile(case+r'\launch_input.dat')
def norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert norm(System.IO.File.ReadAllText(case+r'\launch_input.dat'))==norm(System.IO.File.ReadAllText(case+r'\modal_input.dat'))
System.IO.File.WriteAllText(case+r'\SOLVE_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
baseline.Solve(True)
System.IO.File.WriteAllText(case+r'\SOLVE_RETURNED.txt',unicode(baseline.Solution.Status))
execfile(PCB670_RUN+r'\export_default_results.py')
