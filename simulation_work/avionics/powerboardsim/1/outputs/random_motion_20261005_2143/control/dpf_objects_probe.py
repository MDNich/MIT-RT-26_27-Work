import clr,sys,os,System,traceback
p=r'C:\Program Files\ANSYS Inc\v261';b=p+r'\aisol\bin\winx64';sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf
dpf.DataProcessingCore.Initialization()
for typ in [dpf.FieldsFactory,dpf.Field,dpf.FieldsContainer,dpf.Workflow,dpf.TimeFreqSupport]:
 print('TYPE '+str(typ))
 t=clr.GetClrType(typ)
 for m in t.GetConstructors(): print(m)
 for m in t.GetMethods():
  if any(x in m.Name for x in ['Create','Add','Set','Data','Scoping','Warp','Contour','Time','Record']):print(m)
