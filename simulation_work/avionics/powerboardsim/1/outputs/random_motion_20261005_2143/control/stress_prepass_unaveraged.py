import clr,sys,os,System,traceback
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
dpf.DataProcessingCore.Initialization()
import pcb_stress_motion as sm
import json,time
out='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\dpf_stress_unaveraged_frames.json'
rows=[];start=time.time()
for n in range(1,481):
 color,warp=sm.fields(n)
 rows.append(sm.last)
 if n%20==0:
  print('STRESS '+str(n)+' '+str(time.time()-start));sys.stdout.flush()
  open(out+'.partial.json','w').write(json.dumps(rows))
 del color,warp
 if n%20==0:System.GC.Collect()
open(out,'w').write(json.dumps(rows))
print('COMPLETE')
