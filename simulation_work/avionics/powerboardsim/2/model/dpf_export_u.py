"""Run with the installed ANSYS IronPython/DPF runtime, independently of MAPDL."""
import os,sys,clr,System,json
from System import Array,Double,Int32,Byte,Buffer
from System.IO import File
p=r'C:\Program Files\ANSYS Inc\v261'
b=p+r'\aisol\bin\winx64'
sys.path.append(b)
os.environ['PATH']=';'.join([b,p+r'\dpf\bin\winx64',p+r'\Framework\bin\win64',p+r'\tp\IntelCompiler\2023.1.0\winx64',p+r'\tp\IntelMKL\2024.2.3\winx64',os.environ['PATH']])
os.environ['ANSYSCL261_DIR']=p+r'\licensingclient'
os.environ['OMP_NUM_THREADS']='1'
clr.AddReferenceToFileAndPath(b+r'\CS_DataProcessing.dll')
import Ans.DataProcessing as dpf

def binary(path,a,typ):
    v=Array[typ](a);size=Buffer.ByteLength(v)
    raw=Array.CreateInstance(Byte,size);Buffer.BlockCopy(v,0,raw,0,size)
    tmp=path+'.tmp';File.WriteAllBytes(tmp,raw);os.rename(tmp,path)
    return len(v)

def main(rst,out):
    spec=json.load(open(os.path.join(out,'request.json')))
    dpf.DataProcessingCore.Initialization()
    ds=dpf.DataSources(rst)
    field=spec.get('field','U')
    expected=spec.get('unit','m')
    assert (field,expected) in [('U','m'),('U','mm'),('ROT','rad')]
    suffix='.rot' if field=='ROT' else '.u'
    for k in spec['sets']:
        stem=os.path.join(out,'set_%04d'%k)
        if os.path.exists(stem+'.json'):continue
        ts=dpf.Scoping();ts.Ids=[k];op=dpf.Operator(field);op.Connect(4,ds);op.Connect(0,ts)
        fc=op.GetOutputAsFieldsContainer(0)
        assert fc.FieldCount==1
        f=fc[0];unit=str(f.Unit);assert unit.strip().lower()==expected,unit
        ids=binary(stem+'.ids',f.ScopingIds,Int32);values=binary(stem+suffix,f.Data,Double)
        assert values==3*ids
        info=dict(set=k,nodes=ids,unit=unit,components=3,source_sha256=spec['source_sha256'])
        if 'field' in spec:info['field']=field
        with open(stem+'.json.tmp','w') as s:json.dump(info,s)
        os.rename(stem+'.json.tmp',stem+'.json')
    print('DPF_U_EXPORT_DONE')

if __name__=='__main__':main(*sys.argv[1:])
