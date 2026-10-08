import clr,sys,os,System
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=b+';'+p+r'\dpf\bin\winx64;'+os.environ['PATH']
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf

for c in [dpf.DataProcessingCore,dpf.Core,dpf.RuntimeConfig,dpf.RuntimeCoreConfig,dpf.Session]:
 print(c)
 for m in clr.GetClrType(c).GetMethods(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.DeclaredOnly):print(m)
 for m in clr.GetClrType(c).GetConstructors():print(m)
