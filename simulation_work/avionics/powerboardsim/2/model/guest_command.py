import base64,sys,subprocess
args=['prlctl','exec','Windows 11 (1)']
if '--user' in sys.argv:args.append('--current-user')
ps="$ProgressPreference='SilentlyContinue';\n"+sys.stdin.read()
p=subprocess.run(args+['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],capture_output=True,timeout=100)
print(p.stdout.decode(errors='replace').strip())
if p.returncode:print(p.stderr.decode(errors='replace')[:1800])
sys.exit(p.returncode)
