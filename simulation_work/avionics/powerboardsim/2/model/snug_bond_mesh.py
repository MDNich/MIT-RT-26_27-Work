"""Compare bond histories on matching installed 2 and 1.5 mm case meshes."""
import argparse
import hashlib
import numpy as np

from audit_local import ROOT, read
from case_stress import source as native_source
from cell_attachment_force import bodies_and_bonds
from film_identity import digest, verified, write_json
from stage_snug_fit import AUDIT


def compare(material):
    base='snug125_'+material
    variants=(base,base+'_mesh15')
    matched_path=AUDIT/(material+'_modal_mesh_comparison.json')
    matched=read(matched_path)['models']
    assert [m['mesh_size_mm'] for m in matched]==[2,1.5]
    cells=[]
    footprints=[]
    for variant,model in zip(variants,matched,strict=True):
        source=read(ROOT/'validation/cell_attachment'/(variant+'.json'))
        assert source['modal_rst_sha256']==model['basis_rst_sha256']
        inertia_path=ROOT/'validation/cell_force'/(variant+'.json')
        verified(inertia_path,source['cell_inertia_record_sha256'])
        inertia=read(inertia_path)
        cells.append((source,inertia))
        proof,_,rst=native_source(variant+'_basis',source['campaign'])
        assert proof['rst_sha256']==model['basis_rst_sha256']
        _,pairs,_=bodies_and_bonds(rst,inertia['geometry'])
        footprints.append({str(pair):{str(material):hashlib.sha256(np.asarray(nodes,dtype='<i8').tobytes()).hexdigest()
                                      for material,nodes in sides} for pair,sides in pairs.items()})
        del rst
    # Cell meshes, material mass and both bond areas are inherited from the same installed assembly.
    assert cells[0][1]['geometry']==cells[1][1]['geometry'] and footprints[0]==footprints[1]
    ratios={}
    for axis in 'XYZ':
        rows=[]
        for (source,inertia),variant in zip(cells,variants,strict=True):
            path=AUDIT/f'{variant}_{axis}_bond_independent.json'
            exact_path=AUDIT/f'{variant}_{axis}_bond_exact.json'
            nominal,exact=read(path),read(exact_path)
            assert nominal['basis_rst_sha256']==exact['basis_rst_sha256']==inertia['basis_rst_sha256']
            assert nominal['axis']==exact['axis']==axis and nominal['method']=='independent' and exact['method']=='exact'
            assert nominal['load_sha256']==exact['load_sha256']
            ends={body:[(e['pair'],e['strip_material'],e['cell_nodes'],e['nickel_nodes']) for e in r['ends']]
                  for body,r in source['spectrum'][axis]['cells'].items()}
            rows.append(dict(inputs=[digest(path),digest(exact_path)],bonds=ends,
                             load_sha256=nominal['load_sha256'],governing_bond=nominal['largest_bond'],
                             middle_at_its_peak=nominal['middle_cell_at_its_largest_bond'],
                             peak_pocket_N=nominal['pocket_maximum']['magnitude_N'],
                             exact_peak_N=exact['largest_bond']['magnitude_N'],
                             exact_pair=exact['largest_bond']['pair'],modes=nominal['modes']))
        coarse,fine=rows
        assert coarse['bonds']==fine['bonds'] and coarse['load_sha256']==fine['load_sha256']
        def field(row):
            return row['governing_bond']['magnitude_N']
        ratios[axis]=dict(nominal=coarse,fine=fine,change_in_peak_bond_percent=100*(field(fine)/field(coarse)-1),
                          change_in_peak_pocket_percent=100*(fine['peak_pocket_N']/coarse['peak_pocket_N']-1),
                          maximum_integration_difference_percent=max(100*abs(r['exact_peak_N']/field(r)-1) for r in rows))
    write_json(AUDIT/f'{material}_bond_mesh_comparison.json',dict(material=material,matched_basis_sha256=digest(matched_path),
               ordered_interface_node_sha256=footprints[0],axes=ratios,scope='Independent integration of the matched native prestressed modes at two case mesh '
                                'sizes. Both original nickel attachment footprints on each of the three cells are retained. '
                                'The contacts stay fixed within each run. Peak times and governing bonds can change.'))
    for axis,row in ratios.items():
        print(axis,row['nominal']['governing_bond']['magnitude_N'],row['fine']['governing_bond']['magnitude_N'],
              row['change_in_peak_bond_percent'],row['fine']['governing_bond']['cell'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('material',choices=('nylon','aluminium'))
    compare(parser.parse_args().material)
