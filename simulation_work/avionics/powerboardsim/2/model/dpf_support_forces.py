"""Read translational reactions at the specified support nodes from a stationary local RST using DPF."""
import json
import os
import sys
from dpf_export_u import dpf


def export(path, out):
    with open(os.path.join(out,'request.json')) as stream:
        spec=json.load(stream)
    dpf.DataProcessingCore.Initialization()
    data=dpf.DataSources(path)
    nodes=dpf.Scoping();nodes.Location='Nodal';nodes.Ids=spec['nodes']
    rows=[]
    for k in spec['sets']:
        selected=dpf.Scoping();selected.Ids=[k]
        operator=dpf.Operator('RF')
        operator.Connect(4,data);operator.Connect(0,selected);operator.Connect(1,nodes)
        fc=operator.GetOutputAsFieldsContainer(0)
        assert fc.FieldCount==1
        field=fc[0]
        unit=str(field.Unit).strip()
        ids=list(field.ScopingIds);values=list(field.Data)
        assert unit=='N' and len(values)==3*len(ids) and len(ids)==len(set(ids))
        assert set(ids).issubset(set(spec['nodes']))
        rows.append(dict(native_set=k,forces_N={str(n):values[3*i:3*i+3] for i,n in enumerate(ids)}))
    dest=os.path.join(out,'forces.json')
    with open(dest+'.tmp','w') as stream:
        json.dump(dict(source_sha256=spec['source_sha256'],sets=rows),stream)
    os.rename(dest+'.tmp',dest)
    print('DPF_SUPPORT_FORCES_DONE')


if __name__=='__main__':export(*sys.argv[1:])
