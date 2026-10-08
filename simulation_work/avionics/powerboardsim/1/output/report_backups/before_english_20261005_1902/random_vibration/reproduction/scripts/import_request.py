from rv_paths import *
import sys,json,subprocess
axis=sys.argv[1]
C=Path((R/axis/'accepted_native_directory.txt').read_text())
assert (C/'NATIVE_SOLVED.txt').exists()
manifest=json.loads((C/'native_solver_audit.json').read_text())
assert manifest['errors']==0 and manifest['axis']==axis
runtime=win(C)
assert 'outputs\\random_vibration' in runtime.lower() and 'dp0' not in runtime.lower()
source="""
ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
a=rvs[INDEX]
assert System.IO.File.Exists(r'ARCHIVE\\NATIVE_SOLVED.txt')
assert System.IO.File.Exists(r'RUNTIME\\file.rst')
a.Solution.ReadGivenAnsysResultFileByReference(r'RUNTIME\\file.rst',Ansys.Mechanical.DataModel.Enums.UnitSystemIDType.UnitsMKS)
assert unicode(a.Solution.ObjectState)=='Solved'
RV_CASE_AXIS='AXIS'
""".replace('INDEX',str(['X','Y','Z'].index(axis))).replace('ARCHIVE',win(C)).replace('RUNTIME',runtime).replace("'AXIS'",repr(axis))
source+=Path('/tmp/rv_post.py').read_text()
z=subprocess.run(['python3','/tmp/pcb_request.py'],input=source,text=True,capture_output=True)
print(z.stdout,z.stderr);z.check_returncode()
