import Ans.DataProcessing as dpf
import System,math
u_basis=None
color=None
last={}

def fields(index):
 global u_basis,color,last
 if u_basis is None:
  op=dpf.Operator('U');op.Connect(4,dpf.DataSources(r'C:\Temp\PBMotion_modal20\file.rst'))
  ts=dpf.Scoping();ts.Ids=[20];op.Connect(0,ts);u_basis=op.GetOutputAsFieldsContainer(0)
  norm=dpf.Operator('norm_fc');norm.Connect(0,u_basis);color=norm.GetOutputAsFieldsContainer(0)
 phase=2*math.pi*index/180.;factor=math.sin(phase)
 scale=dpf.Operator('scale_fc');scale.Connect(0,u_basis);scale.Connect(1,factor);warp=scale.GetOutputAsFieldsContainer(0)
 mm=dpf.Operator('min_max_fc');mm.Connect(0,color);maximum=list(mm.GetOutputAsField(1).Data)[0]
 assert abs(maximum-7.160033972903191)<1e-5
 last={'frame':index,'phase_radian':phase,'phase_factor':factor,'normalized_maximum':maximum,'nodes':{n:list(warp[0].GetEntityDataById(n)) for n in [44,2064,2075,2185,42154,42242,136765]}}
 return color,warp

def workflow(obj):
 index=int(System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\modal_frame.txt'))
 color,warp=fields(index)
 co=dpf.Operator('forward_fc');co.Connect(0,color)
 n=42242;expected=[v*1000 for v in warp[0].GetEntityDataById(n)]
 wo=dpf.Operator('unit_convert_fc');wo.Connect(0,warp);wo.Connect(1,'mm')
 converted=wo.GetOutputAsFieldsContainer(0);assert converted[0].Unit=='mm'
 actual=list(converted[0].GetEntityDataById(n))
 assert max(abs(a-b) for a,b in zip(actual,expected))<1e-8*max(1,max(abs(b) for b in expected))
 last['graphics_warp_unit']='mm';last['graphics_unit_conversion']=1000
 wf=dpf.Workflow();wf.Add(co);wf.Add(wo);wf.SetOutputContour(co,dpf.enums.GFXContourType.GeomBodyScoping);wf.SetOutputWarpField(wo)
 wf.Record('pb_modal20_phase_%d'%index,True);obj.WorkflowId=wf.GetRecordedId()
 System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\modal_last.txt',repr(last))
 return wf
