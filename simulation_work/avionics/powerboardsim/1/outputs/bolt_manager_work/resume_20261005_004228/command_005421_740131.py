import System
assert System.IO.File.Exists(PCB670_RUN+r'\default\PREFLIGHT_PASSED.txt')
assert baseline.AnalysisSettings.MaximumModesToFind==20 and baseline.AnalysisSettings.Damped==False
assert baseline.AnalysisSettings.SearchRangeMinimum.Value==1
assert all(o.Suppressed for o in list(manager.Children))
# Re-export and compare byte-for-byte with the checked native input.
bm=e.GetModule().ApdlBoltModule;bm.StartApdlInputFileWrite(baseline)
baseline.WriteInputFile(PCB670_RUN+r'\default\launch_input.dat')
a=System.IO.File.ReadAllText(PCB670_RUN+r'\default\modal_input.dat');b=System.IO.File.ReadAllText(PCB670_RUN+r'\default\launch_input.dat')
# Export timestamp comments may vary; all command/data records must match.
def norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert norm(a)==norm(b),'Input changed since preflight'
System.IO.File.WriteAllText(PCB670_RUN+r'\default\SOLVE_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
baseline.Solve(False)
