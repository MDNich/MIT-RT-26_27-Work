import sys,subprocess,base64,os
ps='[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ProgressPreference="SilentlyContinue"; '+sys.stdin.read()
session=os.environ.get('PCB_VM_EXEC_SESSION','current-user')
assert session in ('current-user','system'),session
args=['/usr/local/bin/prlctl','exec','Windows 11']
if session=='current-user':args.append('--current-user')
r=subprocess.run(args+['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],capture_output=True,text=True,errors='replace',timeout=50)
print(r.stdout)
if r.returncode:print(r.stderr)
sys.exit(r.returncode)
