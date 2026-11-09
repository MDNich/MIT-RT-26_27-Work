"""Native IronPython/DPF readback for selected local tab and pilot nodes. No structural solve."""
import os,sys,json,struct
from dpf_export_u import dpf
def run(path,out):
    q=json.load(open(os.path.join(out,'request.json')))
    dpf.DataProcessingCore.Initialization();src=dpf.DataSources(path)
    points=dpf.Scoping();points.Location='Nodal';points.Ids=q['nodes']
    binary=os.path.join(out,'displacements.bin')
    with open(binary+'.tmp','wb') as b:
        for k in q['sets']:
            ts=dpf.Scoping();ts.Ids=[k];u=dpf.Operator('U');u.Connect(4,src);u.Connect(0,ts);u.Connect(1,points)
            fc=u.GetOutputAsFieldsContainer(0);assert fc.FieldCount==1
            f=fc[0];unit=str(f.Unit).strip()
            assert unit.lower() in ['m','mm']
            assert set(f.ScopingIds)==set(q['nodes'])
            raw=list(f.Data);ids=list(f.ScopingIds);assert len(raw)==3*len(ids)
            ix=dict((n,i) for i,n in enumerate(ids))
            for n in q['nodes']:
                i=3*ix[n];b.write(struct.pack('<ddd',*raw[i:i+3]))
    os.rename(binary+'.tmp',binary)
    meta=dict(unit=unit,nodes=len(q['nodes']),sets=q['sets'],source_sha256=q['source_sha256'])
    dest=os.path.join(out,'done.json')
    with open(dest+'.tmp','w') as s:json.dump(meta,s)
    os.rename(dest+'.tmp',dest)
    print('DPF_TAB_POINTS_DONE')
if __name__=='__main__':run(*sys.argv[1:])
