ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
assert System.IO.File.Exists(RV_ROOT+r'\modal_basis\PREFLIGHT_PASSED.txt')
assert unicode(ExtAPI.DataModel.GetObjectById(4123).Solution.ObjectState)=='Solved'
assert rvmodal.AnalysisSettings.MaximumModesToFind==60
assert rvmodal.AnalysisSettings.SearchRangeMinimum.Value==1
assert rvmodal.AnalysisSettings.SearchRangeMaximum.Value==4000
assert not rvmodal.AnalysisSettings.Damped
assert rvmodal.AnalysisSettings.Stress and rvmodal.AnalysisSettings.Strain
assert all(not o.Suppressed for o in list(manager.Children))
bm.StartApdlInputFileWrite(rvmodal)
rvmodal.WriteInputFile(RV_ROOT+r'\modal_basis\launch_input.dat')
def rv_norm(x):return u'\n'.join(l for l in x.splitlines() if not l.lstrip().startswith('!'))
assert rv_norm(System.IO.File.ReadAllText(RV_ROOT+r'\modal_basis\modal_input.dat'))==rv_norm(System.IO.File.ReadAllText(RV_ROOT+r'\modal_basis\launch_input.dat')),'Input changed since preflight'
System.IO.File.WriteAllText(RV_ROOT+r'\modal_basis\SOLVE_STARTED.txt',System.DateTime.UtcNow.ToString('o'))
rvmodal.Solve(True)
System.IO.File.WriteAllText(RV_ROOT+r'\modal_basis\SOLVE_RETURNED.txt',unicode(rvmodal.Solution.Status)+'\n'+unicode(rvmodal.Solution.ObjectState))
assert unicode(rvmodal.Solution.ObjectState)=='Solved'
reader=rvmodal.GetResultsData()
freqs=list(reader.ListTimeFreq)
System.IO.File.WriteAllText(RV_ROOT+r'\modal_basis\frequencies.csv','rank,frequency_hz\n'+'\n'.join('%s,%.12g'%(i+1,f) for i,f in enumerate(freqs)))
assert len(freqs)>=20 and max(freqs)>=3000 and min(freqs)>=1
for name in ['ds.dat','solve.out','file.rst','file.err','file.mode','file.full','file.db','file.esav']:
 src=System.IO.Path.Combine(rvmodal.WorkingDir,name)
 if System.IO.File.Exists(src):System.IO.File.Copy(src,System.IO.Path.Combine(RV_ROOT,'modal_basis',name),True)
System.IO.File.WriteAllText(RV_ROOT+r'\modal_basis\MODAL_VERIFIED.txt','%s modes, max %.9g Hz'%(len(freqs),max(freqs)))
ExtAPI.Application.ScriptByName('journaling').ExecuteCommandAsync('Save(Overwrite=True)')
