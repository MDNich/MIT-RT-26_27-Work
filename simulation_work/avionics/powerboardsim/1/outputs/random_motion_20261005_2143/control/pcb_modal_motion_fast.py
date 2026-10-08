import Ans.DataProcessing as dpf

def workflow(obj):
 u=dpf.Operator('U');u.Connect(4,dpf.DataSources(r'C:\Temp\PBMotion_modal20\file.rst'))
 ts=dpf.Scoping();ts.Ids=[20];u.Connect(0,ts)
 color=dpf.Operator('norm_fc');color.Connect(0,u)
 warp=dpf.Operator('scale_fc');warp.Connect(0,u);warp.Connect(1,0.0)
 wf=dpf.Workflow();wf.Add(u);wf.Add(color);wf.Add(warp)
 wf.SetInputName(warp,1,'phase');wf.SetOutputName(warp,0,'warp_audit');wf.SetOutputName(color,0,'color_audit')
 wf.SetOutputContour(color,dpf.enums.GFXContourType.GeomBodyScoping);wf.SetOutputWarpField(warp)
 wf.Record('pb_modal_fast',True);obj.WorkflowId=wf.GetRecordedId()
