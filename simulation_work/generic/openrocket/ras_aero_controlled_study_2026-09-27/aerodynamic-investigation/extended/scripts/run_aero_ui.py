import sys,time,json,subprocess,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/windows-ui'))
from ui import ui,capture
R=Path(__file__).resolve().parents[1]
WIN=r'C:\Users\Public\Documents\CodexRASAeroStudy\extended'
PID=15160
def snap():
 text=ui('snap',PID);ans=[]
 for line in text.splitlines():
  p=line.split('|',3)
  if len(p)==4:ans.append((int(p[0]),p[1],tuple(map(int,p[2].split(','))),p[3]))
 return ans
def window(title):
 for i in range(12):
  found=[e for e in snap() if e[3]==title]
  if found:return found[0]
  time.sleep(.3)
 raise RuntimeError('Missing window: '+title)
def close_aero():
 for e in snap():
  if e[3]=='Aero Plots':
   l,t,r,b=e[2];ui('click',r-33,t+28)
def run(name):
 close_aero();ui('keys','^o');ui('paste',WIN+'\\'+name+'.CDX1');ui('keys','{ENTER}')
 time.sleep(.25)
 entries=snap();assert any(e[3]==name for e in entries),(name,'not loaded')
 ui('click',780,125);e=window('Aero Plots');l,t,r,b=e[2]
 ui('click',l+66,t+82);ui('click',l+141,t+130);ui('click',l+430,t+133)
 ui('paste',WIN+'\\'+name+'.csv');ui('keys','{ENTER}')
 time.sleep(.2);window('Aero Plots')
 capture();shutil.copy2('/tmp/rasaero-comparison/windows.png',R/'evidence'/(name+'-aero.png'))
 close_aero()
 print('EXPORTED '+name,flush=True)
if __name__=='__main__':
 names=sys.argv[1:] or (R/'new-cases.txt').read_text().splitlines()
 for name in names:run(name)
 target='\\\\Mac\\Home\\'+str((R/'rasaero').relative_to('/Users/mdn')).replace('/','\\')
 cmd=['prlctl','exec','Windows 11','cmd.exe','/c','copy',WIN+'\\*.csv',target]
 subprocess.run(cmd,check=True,capture_output=True)
