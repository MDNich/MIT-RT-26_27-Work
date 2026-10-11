from pathlib import Path
import sys,datetime
w=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1/outputs/bolt_manager_work');r=Path((w/'latest_resume.txt').read_text());source=sys.stdin.read();t=datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S_%f');(r/('command_'+t+'.py')).write_text(source)
if (r/'request.py').exists():raise RuntimeError('Previous request not consumed')
for n in ['request_done.txt','request_error.txt']:
 p=r/n
 if p.exists():p.rename(r/(t+'_'+n))
(r/'request.tmp').write_text(source);(r/'request.tmp').rename(r/'request.py');print(t)
