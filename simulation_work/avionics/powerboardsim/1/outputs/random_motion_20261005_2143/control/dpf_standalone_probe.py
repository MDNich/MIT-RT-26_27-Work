import clr,sys,os,System
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=b+';'+p+r'\dpf\bin\winx64;'+os.environ['PATH']
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
print('DPF namespace imported')
print(dir(dpf))
