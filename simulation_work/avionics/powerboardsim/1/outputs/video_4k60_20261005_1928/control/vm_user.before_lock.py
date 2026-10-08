import sys,base64,subprocess
s=sys.stdin.read()
r=subprocess.run(["prlctl","exec","{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}","--current-user","powershell.exe","-NoProfile","-EncodedCommand",base64.b64encode(s.encode("utf-16le")).decode()],capture_output=True,text=True,errors="replace",timeout=45)
print(r.stdout,end="");print(r.stderr,file=sys.stderr,end="");sys.exit(r.returncode)
