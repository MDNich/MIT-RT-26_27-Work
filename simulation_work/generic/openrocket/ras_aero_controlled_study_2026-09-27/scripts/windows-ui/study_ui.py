import sys,time,subprocess,shutil
from pathlib import Path
sys.path.insert(0,'/tmp/rasaero-comparison')
from ui import ui,capture
OUT=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/generic/openrocket/ras_aero_controlled_study_2026-09-27')
WIN=r'C:\Users\Public\Documents\CodexRASAeroStudy'
PID=5348

def snap():
 s=ui('snap',PID)
 entries=[]
 for line in s.splitlines():
  parts=line.split('|',3)
  if len(parts)==4:
   h,cl,b,t=parts;entries.append((int(h),cl,tuple(map(int,b.split(','))),t))
 return entries

def click_text(text):
 matches=[x for x in snap() if x[3]==text]
 assert len(matches)==1,(text,matches)
 l,t,r,b=matches[0][2];ui('click',(l+r)//2,(t+b)//2)

def shot(name):
 capture();shutil.copy2('/tmp/rasaero-comparison/windows.png',OUT/'evidence'/f'{name}.png')

def export_done(name):
 click_text('Done');ui('paste',WIN+'\\'+name+'.csv');ui('keys','{ENTER}')
 entries=snap();assert not any(e[3]=='Mentés másként' for e in entries)

def export_plot(name):
 ui('click',224,242);ui('click',325,286);ui('click',506,290);export_done(name)

def save_model(name):
 ui('click',1628,133)
 if any(x[3]=='&Igen' for x in snap()):click_text('&Igen')
 ui('keys','^s');ui('keys','^a');ui('paste',WIN+'\\'+name+'.CDX1');ui('keys','{ENTER}')
 if any(x[3]=='&Igen' for x in snap()):click_text('&Igen')

def copyback(name,where):
 dest=OUT/where/name
 src=WIN+'\\'+name;dst='\\\\Mac\\Home\\'+str(dest.relative_to('/Users/mdn')).replace('/','\\')
 r=subprocess.run(['prlctl','exec','Windows 11','cmd.exe','/c','copy',src,dst],capture_output=True,check=True);print(name,r.stdout.decode().strip())

if __name__=='__main__':
 export_done('B01-smooth-square-I500T-14A')
 ui('click',2194,186);ui('click',1550,385)
 export_plot('B01-smooth-square-J570W')
 ui('click',2194,186);shot('B01-rasaero-summary');save_model('B01-smooth-square')
 for n in ['B01-smooth-square-I500T-14A.csv','B01-smooth-square-J570W.csv']:copyback(n,'rasaero')
 copyback('B01-smooth-square.CDX1','models')
