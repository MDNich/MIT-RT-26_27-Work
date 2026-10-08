# Local Mechanical solves require wait=True; previous async request did not launch MAPDL.
assert all(o.Suppressed for o in list(manager.Children))
System.IO.File.WriteAllText(PCB670_RUN+r'\default\SOLVE_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
baseline.Solve(True)
System.IO.File.WriteAllText(PCB670_RUN+r'\default\SOLVE_RETURNED.txt',unicode(baseline.Solution.Status)+'\n'+unicode(baseline.Solution.ObjectState))
