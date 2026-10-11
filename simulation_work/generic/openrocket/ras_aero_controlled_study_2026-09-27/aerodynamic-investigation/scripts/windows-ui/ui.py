import subprocess,sys,time,pathlib,json
result=pathlib.Path('/Users/mdn/.cache/codex-rasaero-ui-result.txt')
def ui(*args):
 result.unlink(missing_ok=True)
 for attempt in range(3):
  r=subprocess.run(['prlctl','exec','Windows 11','--current-user',r'C:\Users\Public\Documents\CodexRASAero\uiw.exe',*map(str,args)],capture_output=True)
  if r.returncode==0 or result.exists():break
  if r.returncode!=255 or attempt==2:r.check_returncode()
  time.sleep(.5)
 for i in range(100):
  if result.exists():
   time.sleep(.15)
   s=result.read_text();print(s,end='');return s
  time.sleep(.1)
 raise TimeoutError(args)
def capture(): subprocess.run(['prlctl','capture','Windows 11','--file','/tmp/rasaero-comparison/windows.png'],check=True,capture_output=True)
if __name__=='__main__':
 for a in json.load(sys.stdin):ui(*a)
 capture()
