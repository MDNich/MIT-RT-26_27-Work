import System,clr,mech_dpf
import Ans.DataProcessing as dpf
mech_dpf.setExtAPI(ExtAPI)
rows=[]
for n in ['STRESS','MODAL']:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(pbmotionroot+'\\control\\'+n+'_RESULT_ID.txt')))
 rows.append(n+' '+str(r.ObjectId))
 rows.append(str(r.PropertyProviderText))
 for p in r.Properties:
  try:rows.append(str(p.Name)+' = '+str(p.Value))
  except:pass
 try:rows.append('Custom scale '+str(r.GetCustomPropertyByPath('Result Scaling/Activate Result Scaling').ValueString))
 except:rows.append('No property provider')
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
rows.extend(['Scale setting '+str(pref.DeformationScaling),'Multiplier '+str(pref.DeformationScaleMultiplier)])
rows.extend([str(m) for m in clr.GetClrType(dpf.Workflow).GetMethods() if 'Warp' in str(m) or 'Contour' in str(m)])
System.IO.File.WriteAllLines(pbmotionroot+r'\control\warp_probe.txt',rows)
