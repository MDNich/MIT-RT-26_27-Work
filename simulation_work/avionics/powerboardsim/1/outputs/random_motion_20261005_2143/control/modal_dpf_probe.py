import clr,sys,os,System,traceback
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
dpf.DataProcessingCore.Initialization()
import pcb_modal_motion as mm
rows=[]
for i in [0,45,90,135,179]:
 mm.fields(i);rows.append(mm.last)
import json
open('Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\pilot_modal_dpf\\dpf_nodes.json','w').write(json.dumps(rows))
print('MODAL PROBE COMPLETE')
