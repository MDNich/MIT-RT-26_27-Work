import Ans.DataProcessing as dpf
import motion_q_X
basis=None
frame=1
last={}

def fields(number):
 global basis,last
 if basis is None:
  src=dpf.DataSources(r'C:\Temp\PCBRV_20261005_X_local\file.rst')
  s=dpf.Operator('S');ts=dpf.Scoping();ts.Ids=range(1,39)
  es=dpf.Scoping();es.Location='Elemental';es.Ids=range(73331,112345)
  s.Connect(4,src);s.Connect(0,ts);s.Connect(1,es);s.Connect(9,'ElementalNodal')
  basis=s.GetOutputAsFieldsContainer(0)
 q=dpf.FieldsFactory.CreateScalarField(38,'Nodal');q.ScopingIds=range(1,39);q.Data=motion_q_X.rows[number-1]
 qfc=dpf.FieldsContainer();qfc.AddLabel('time');qfc.AddFieldByTimeId(q,1)
 comb=dpf.Operator('expansion::modal_superposition');comb.Connect(0,basis);comb.Connect(1,qfc)
 stress=comb.GetOutputAsFieldsContainer(0)
 eqv=dpf.Operator('eqv_fc');eqv.Connect(0,stress);color=eqv.GetOutputAsFieldsContainer(0)
 u=dpf.Operator('U');u.Connect(4,dpf.DataSources(r'C:\Temp\PBMotion_20261005_expand_X\file.rst'))
 ts=dpf.Scoping();ts.Ids=[number];u.Connect(0,ts);warp=u.GetOutputAsFieldsContainer(0)
 mm=dpf.Operator('min_max_fc');mm.Connect(0,color)
 last={'frame':number,'time_s':1+number/16384.,'maximum_Pa':list(mm.GetOutputAsField(1).Data)[0], 'minimum_Pa':list(mm.GetOutputAsField(0).Data)[0], 'stress_nodes':{},'u_nodes':{}}
 ns=dpf.Scoping();ns.Location='Nodal';ns.Ids=[149869,173651]
 avgcheck=dpf.Operator('to_nodal_fc');avgcheck.Connect(0,stress);avgcheck.Connect(2,ns);nodalcheck=avgcheck.GetOutputAsFieldsContainer(0)
 for n in [149869,173651]:last['stress_nodes'][n]=list(nodalcheck[0].GetEntityDataById(n))
 last['stress_location']='ElementalNodal; no nodal averaging in contour'
 last['element_count']=len(color[0].ScopingIds)
 for n in [44,2064,2075,2185,42154,42242,136765]:last['u_nodes'][n]=list(warp[0].GetEntityDataById(n))
 return color,warp

def workflow(obj):
 import System
 number=int(System.IO.File.ReadAllText(r'C:\Temp\PBMotionControl\stress_frame.txt'))
 color,warp=fields(number)
 co=dpf.Operator('forward_fc');co.Connect(0,color)
 n=42242;expected=[v*1000 for v in warp[0].GetEntityDataById(n)]
 wo=dpf.Operator('unit_convert_fc');wo.Connect(0,warp);wo.Connect(1,'mm')
 converted=wo.GetOutputAsFieldsContainer(0);assert converted[0].Unit=='mm'
 actual=list(converted[0].GetEntityDataById(n))
 assert max(abs(a-b) for a,b in zip(actual,expected))<1e-8*max(1,max(abs(b) for b in expected))
 last['graphics_warp_unit']='mm';last['graphics_unit_conversion']=1000
 wf=dpf.Workflow();wf.Add(co);wf.Add(wo);wf.SetOutputContour(co,dpf.enums.GFXContourType.GeomBodyScoping);wf.SetOutputWarpField(wo)
 wf.Record('pb_stress_motion_%d'%number,True);obj.WorkflowId=wf.GetRecordedId()
 System.IO.File.WriteAllText(r'C:\Temp\PBMotionControl\stress_last.txt',repr(last))
 return wf
