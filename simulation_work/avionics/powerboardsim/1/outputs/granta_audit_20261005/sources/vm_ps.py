import sys,subprocess,base64
ps='[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ProgressPreference="SilentlyContinue"; '+sys.stdin.read()
r=subprocess.run(['/usr/local/bin/prlctl','exec','Windows 11','--current-user','powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],capture_output=True,text=True,errors='replace')
print(r.stdout)
if r.returncode:print(r.stderr)
sys.exit(r.returncode)
