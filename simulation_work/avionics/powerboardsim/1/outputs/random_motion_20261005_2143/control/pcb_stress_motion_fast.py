import Ans.DataProcessing as dpf
import motion_q_X

def coordinates(number):
 q=dpf.FieldsFactory.CreateScalarField(38,'Nodal');q.ScopingIds=range(1,39);q.Data=motion_q_X.rows[number-1]
 qfc=dpf.FieldsContainer();qfc.AddLabel('time');qfc.AddFieldByTimeId(q,1)
 return qfc

def workflow(obj):
 src=dpf.DataSources(r'C:\Temp\PCBRV_20261005_X_local\file.rst')
 s=dpf.Operator('S');ts=dpf.Scoping();ts.Ids=range(1,39)
 es=dpf.Scoping();es.Location='Elemental';es.Ids=range(73331,112345)
 s.Connect(4,src);s.Connect(0,ts);s.Connect(1,es);s.Connect(9,'ElementalNodal')
 basis=s.GetOutputAsFieldsContainer(0)
 comb=dpf.Operator('expansion::modal_superposition');comb.Connect(0,basis);comb.Connect(1,coordinates(1))
 color=dpf.Operator('eqv_fc');color.Connect(0,comb)
 u=dpf.Operator('U');u.Connect(4,dpf.DataSources(r'C:\Temp\PBMotion_20261005_expand_X\file.rst'))
 ts=dpf.Scoping();ts.Ids=[1];u.Connect(0,ts)
 wf=dpf.Workflow();wf.Add(comb);wf.Add(color);wf.Add(u)
 wf.SetInputName(comb,1,'qfc');wf.SetInputName(u,0,'time')
 wf.SetOutputName(color,0,'color_audit');wf.SetOutputName(u,0,'warp_audit');wf.SetOutputName(comb,0,'stress_audit')
 wf.SetOutputContour(color,dpf.enums.GFXContourType.GeomBodyScoping);wf.SetOutputWarpField(u)
 wf.Record('pb_stress_fast',True);obj.WorkflowId=wf.GetRecordedId()
