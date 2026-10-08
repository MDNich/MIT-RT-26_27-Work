# Caller supplies RV_CASE_AXIS. Only one random-vibration case is solved per invocation.
axis=RV_CASE_AXIS
assert axis in ['X','Y','Z']
a=rvs[['X','Y','Z'].index(axis)]
case=System.IO.Path.Combine(RV_ROOT,axis)
assert System.IO.File.Exists(System.IO.Path.Combine(case,'PREFLIGHT_PASSED.txt'))
assert System.IO.File.Exists(System.IO.Path.Combine(RV_ROOT,'modal_basis','MODAL_VERIFIED.txt'))
assert unicode(rvmodal.Solution.ObjectState)=='Solved'
assert abs(a.AnalysisSettings.ConstantDampingRatio-0.02)<1e-12
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
bm.StartApdlInputFileWrite(a)
a.WriteInputFile(System.IO.Path.Combine(case,'launch_input.dat'))
def rv_norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert rv_norm(System.IO.File.ReadAllText(System.IO.Path.Combine(case,'psd_input.dat')))==rv_norm(System.IO.File.ReadAllText(System.IO.Path.Combine(case,'launch_input.dat'))),'Input changed since preflight'
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'SOLVE_STARTED.txt'),System.DateTime.UtcNow.ToString('o'))
a.Solve(True)
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'SOLVE_RETURNED.txt'),unicode(a.Solution.Status)+'\n'+unicode(a.Solution.ObjectState))
assert unicode(a.Solution.ObjectState)=='Solved'
for name in ['ds.dat','solve.out','file.err']:
 src=System.IO.Path.Combine(a.WorkingDir,name)
 if System.IO.File.Exists(src):System.IO.File.Copy(src,System.IO.Path.Combine(case,name),True)
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'solver_directory.txt'),a.WorkingDir)
# Full binary files stay in each separate new solver directory. Audit hashes are added on host.
System.IO.File.WriteAllText(System.IO.Path.Combine(case,'SOLVED.txt'),System.DateTime.UtcNow.ToString('o'))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
