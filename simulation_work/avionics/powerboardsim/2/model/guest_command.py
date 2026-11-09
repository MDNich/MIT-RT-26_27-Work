import argparse,base64,sys,subprocess
parser=argparse.ArgumentParser();parser.add_argument('--user',action='store_true');parser.add_argument('--timeout',type=int,default=100)
opt=parser.parse_args();assert 1<=opt.timeout<=7200
args=['prlctl','exec','Windows 11 (1)']
if opt.user:args.append('--current-user')
ps="$ProgressPreference='SilentlyContinue';\n"+sys.stdin.read()
p=subprocess.run(args+['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],capture_output=True,timeout=opt.timeout)
print(p.stdout.decode(errors='replace').strip())
if p.returncode:print(p.stderr.decode(errors='replace')[:1800])
sys.exit(p.returncode)
