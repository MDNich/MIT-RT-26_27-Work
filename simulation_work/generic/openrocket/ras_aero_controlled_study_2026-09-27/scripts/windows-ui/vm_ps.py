import base64,subprocess,sys
script=sys.stdin.read()
arg=base64.b64encode(script.encode('utf-16le')).decode()
r=subprocess.run(['prlctl','exec','Windows 11','powershell.exe','-NoProfile','-EncodedCommand',arg],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
print(r.stdout.decode('utf-8',errors='replace'))
sys.exit(r.returncode)
