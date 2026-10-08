import clr,sys,os,System,traceback
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
dpf.DataProcessingCore.Initialization()
ds=dpf.DataSources(r'C:\Temp\PCBRV_20261005_X_local\file.rst')
op=dpf.Operator('S');ts=dpf.Scoping();ts.Ids=range(1,39)
ms=dpf.Scoping();ms.Location='Elemental';ms.Ids=range(73331,112345)
op.Connect(4,ds);op.Connect(0,ts);op.Connect(1,ms);op.Connect(9,'ElementalNodal')
fc=op.GetOutputAsFieldsContainer(0)
print('BASIS '+str(fc.FieldCount))
qrows=[[4.944127e-08, 3.093792e-08, 4.440154e-06, 8.702221e-06, 7.40961e-07, -4.38329e-07, 1.645909e-07, -1.688309e-07, 1.503334e-08, 1.412233e-07, -3.382192e-08, 2.959162e-09, -1.735085e-08, -3.806802e-08, -4.72501e-08, 3.889185e-10, -3.964087e-10, -1.808202e-10, 4.970373e-11, -2.742183e-10, 8.041877e-10, -1.071213e-09, -1.631667e-09, -9.965239e-10, 4.712729e-09, 6.024283e-09, -2.804745e-09, 1.762539e-09, 5.791977e-09, -1.202532e-08, 1.618912e-08, -1.029358e-08, 1.338152e-08, -9.005296e-09, 4.405577e-09, 1.568974e-09, 3.742239e-09, 2.629136e-09], [7.793236e-08, -7.504095e-09, 1.478786e-06, 1.145828e-05, 6.17007e-07, -4.076191e-07, -4.106187e-08, 8.033834e-08, 2.073254e-08, 5.590811e-08, 6.179933e-08, 3.254235e-09, 5.523403e-08, -2.429884e-09, -1.218848e-08, 1.409958e-08, -1.156772e-08, -4.181976e-09, 6.723325e-10, -2.918283e-09, 8.40407e-09, -7.759686e-09, -9.671345e-09, -5.187454e-09, 2.383309e-08, 3.002264e-08, -1.352701e-08, 7.896602e-09, 2.564352e-08, -5.125194e-08, 6.7447e-08, -4.20368e-08, 5.414286e-08, -3.60484e-08, 1.751855e-08, 6.153605e-09, 1.438742e-08, 1.000927e-08]]
qfc=dpf.FieldsContainer();qfc.AddLabel('time')
for i,row in enumerate(qrows):
 f=dpf.FieldsFactory.CreateScalarField(38,'Nodal');f.ScopingIds=range(1,39);f.Data=row
 qfc.AddFieldByTimeId(f,i+1)
print('Q '+str(qfc.FieldCount))
msup=dpf.Operator('expansion::modal_superposition');msup.Connect(0,fc);msup.Connect(1,qfc)
sfc=msup.GetOutputAsFieldsContainer(0)
print(sfc)
avg=dpf.Operator('to_nodal_fc');avg.Connect(0,sfc)
nfc=avg.GetOutputAsFieldsContainer(0)
eqv=dpf.Operator('eqv_fc');eqv.Connect(0,nfc)
efc=eqv.GetOutputAsFieldsContainer(0)
out={'nodes':{},'equivalent':{},'field_units':str(nfc[0].Unit),'ids_count':len(list(nfc[0].ScopingIds))}
for n in [149869,173651]:
 out['nodes'][str(n)]=[list(nfc[i].GetEntityDataById(n)) for i in range(2)]
 out['equivalent'][str(n)]=[list(efc[i].GetEntityDataById(n)) for i in range(2)]
print(out)
import json
open('Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_motion_20261005_2143\\dpf_pcb_proof.json','w').write(json.dumps(out))
print('DONE')
