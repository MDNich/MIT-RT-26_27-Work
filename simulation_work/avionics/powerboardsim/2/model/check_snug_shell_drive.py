"""Independently read the sealed MAPDL arrays and geometry used by both intact-shell controls."""
import re

import numpy as np

from case_stress import source
from audit_local import ROOT,read
from film_identity import verified,write_json,digest
from snug_shell_equilibrium import solid_parts
from stage_snug_fit import AUDIT,INPUTS


def check(variant,campaign):
    registry=AUDIT/(variant+'_shell_inputs_v2.json');specs=read(registry)
    checks={}
    for case,spec in specs.items():
        assert spec['case']==case and spec['variant']==variant and spec['campaign']==campaign
        step=spec['step_sha256']
        p,_,rst=source(spec['static_case'],campaign);assert p['rst_sha256']==spec['static_rst_sha256']
        parts=solid_parts(rst)
        folder=INPUTS/case
        for name,sha in spec['files'].items():verified(folder/name,sha)
        cache=ROOT/'.runtime/shell_fixture'/campaign/variant/'parent_fields.npz';verified(cache,spec['drive_field_sha256'])
        text=(folder/'model.inp').read_text()
        nodes=[];xyz=[]
        for line in re.findall(r'(?im)^n,([^\n]+)',text):
            cols=line.split(',');nodes.append(int(cols[0]));xyz.append(list(map(float,cols[1:])))
        nodes=np.array(nodes);xyz=np.array(xyz);orig=np.searchsorted(rst.mesh.nnum,nodes)
        assert np.array_equal(nodes,rst.mesh.nnum[orig]) and np.max(abs(xyz-rst.mesh.nodes[orig]))<1.e-14
        counts={}
        for match in re.finditer(r'(?im)^et,(\d+),(186|187)\n(.*?)^eblock,(\d+),compact,,(\d+)\n\((\d+)i9\)\n(.*?)^-1$',text,re.S):
            m,typ=int(match[1]),int(match[2]);et,es,conn,_=parts[m]
            width,count=int(match[4]),int(match[5])
            assert et==typ and width==int(match[6])==conn.shape[1]+1 and count==len(es)
            cards=np.fromstring(match[7],sep=' ',dtype=int).reshape(count,width)
            assert np.array_equal(cards[:,0],es) and np.array_equal(cards[:,1:],conn)
            counts[m]=count
        assert counts=={int(k):v for k,v in spec['solids'].items()}
        assert ('type,852' in text)==spec['contact']
        if spec['contact']:
            assert spec['target_material_id']==851
            assert 'mat,851\nesel,s,mat,,173' in text and 'mat,853\nesurf' in text
        with np.load(cache) as saved:
            t=saved['t'];driven=saved['driven'];nt=len(t);n=len(driven)
            assert np.array_equal(nodes,saved['nodes'])
            assert np.array_equal(np.loadtxt(folder/'pbn.dat'),driven)
            assert np.array_equal(np.loadtxt(folder/'pbt.dat'),t)
            coef=np.loadtxt(folder/'pbq.dat').reshape(nt,nt,order='F')
            assert np.array_equal(coef,np.eye(nt))
            ix=np.searchsorted(nodes,driven)
            error=0.
            for j,tag in enumerate('xyz'):
                field=np.loadtxt(folder/('shape'+tag+'.dat')).reshape(nt,n,order='F')
                expected=saved['u'][:,ix,j]
                error=max(error,float(abs(coef@field-expected).max()))
            assert error<1.e-15
        checks[case]=dict(geometry_nodes=len(nodes),solid_elements=sum(counts.values()),checked_drives=n,
                          checked_stations=nt,maximum_serialized_displacement_error_m=error)
    write_json(AUDIT/(variant+'_shell_preflight_v2.json'),dict(variant=variant,campaign=campaign,
               registry_sha256=digest(registry),step_sha256=step,cases=checks,
               scope='Input audit only. The native equilibrium, original contact-face topology, displacement '
                     'recovery and separate interface and hardware reactions are checked after each solve.'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant',choices=('snug125_nylon','snug125_aluminium'))
    parser.add_argument('--campaign',default='nov08_01')
    a=parser.parse_args();check(a.variant,a.campaign)
