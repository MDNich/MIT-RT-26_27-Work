import clr,sys,os,System,traceback
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
try:
 dpf.DataProcessingCore.Initialization()
 print('DPF initialized')
 ds=dpf.DataSources(r'C:\Temp\PCBRV_20261005_X_local\file.rst')
 op=dpf.Operator('S')
 ts=dpf.Scoping();ts.Ids=[1,2]
 ms=dpf.Scoping();ms.Location='Elemental';ms.Ids=[73331,73332]
 op.Connect(4,ds);op.Connect(0,ts);op.Connect(1,ms);op.Connect(9,'ElementalNodal')
 fc=op.GetOutputAsFieldsContainer(0)
 print(fc)
 print(dir(fc))
 print(fc[0])
 print(list(fc[0].Data))
except:
 print(traceback.format_exc())
