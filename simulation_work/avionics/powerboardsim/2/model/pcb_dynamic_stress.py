"""Superpose signed native modal stress tensors at each PCB element corner before computing von Mises."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from native_rst import read_rst

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def cache_modes(rst_path, folder):
    """Keep the identity of each element-corner result even at a shared geometry node."""
    result = read_rst(str(rst_path))
    freq = result.time_values
    if np.any(np.diff(freq) <= 0) or freq[0] <= 0:
        raise ValueError('Use an exclusively modal RST with increasing positive frequencies')
    folder.mkdir(parents=True, exist_ok=True)
    seal = folder/'basis.json'
    checksum = digest(rst_path)
    if seal.exists():
        meta = json.loads(seal.read_text())
        if meta['rst_sha256'] != checksum:
            raise ValueError('Cached basis belongs to a different result file')
        return meta
    grid = result.grid
    pcb = (grid.cell_data['ansys_material_type']==208) & np.isin(grid.cell_data['ansys_elem_type_num'],[185,186,187])
    elements = np.sort(grid.cell_data['ansys_elem_num'][pcb])
    if not len(elements):
        raise ValueError('Missing PCB structural elements')
    tensor = None
    for mode in range(len(freq)):
        enum, stress, corners = result.element_solution_data(mode,'ENS')
        items = np.searchsorted(enum,elements)
        if not np.array_equal(enum[items],elements):
            raise ValueError('Missing element stress records')
        ids = np.concatenate([corners[i] for i in items])
        counts = np.fromiter((len(corners[i]) for i in items),int,count=len(items))
        # ENS starts with the six signed stresses. Each material-frame orientation is
        # constant across modes of this linearized assembly. Von Mises is invariant
        # under the common rotation from the element frame to global coordinates.
        components = np.concatenate([stress[i].reshape(len(corners[i]),-1)[:,:6] for i in items])
        if components.shape != (len(ids),6) or not np.isfinite(components).all():
            raise ValueError(f'Invalid signed stress components in mode {mode+1}')
        if tensor is None:
            labels, multiplicity = ids.copy(),counts.copy()
            tensor = np.lib.format.open_memmap(folder/'tensors.partial.npy',mode='w+',dtype=np.float64,shape=(len(freq),len(ids),6))
        elif not np.array_equal(ids,labels) or not np.array_equal(counts,multiplicity):
            raise ValueError('Element-corner ordering changed between modal sets')
        tensor[mode] = components
    tensor.flush()
    del tensor
    (folder/'tensors.partial.npy').replace(folder/'tensors.npy')
    np.savez(folder/'locations.npz',element=elements,counts=multiplicity,node=labels)
    meta=dict(rst_sha256=checksum,element_count=len(elements),element_corner_records=len(labels),frequencies_Hz=freq.tolist())
    seal.write_text(json.dumps(meta,indent=2)+'\n')
    return meta


def equivalent(t):
    xx,yy,zz,xy,yz,xz = np.moveaxis(t,-1,0)
    return np.sqrt(.5*((xx-yy)**2+(yy-zz)**2+(zz-xx)**2)+3*(xy**2+yz**2+xz**2))


def extrema(tensor, coordinates):
    if coordinates.shape[1]!=tensor.shape[0]:
        raise ValueError('Incompatible modal basis and history')
    # Bounded point blocks let BLAS evaluate the complete movie at once.
    nframes = len(coordinates)
    maximum = np.full(nframes,-np.inf)
    minimum = np.full(nframes,np.inf)
    for start in range(0,tensor.shape[1],2048):
        block = np.ascontiguousarray(tensor[:,start:start+2048]).reshape(len(tensor),-1)
        field = equivalent((coordinates@block).reshape(nframes,-1,6))
        maximum = np.maximum(maximum,field.max(axis=1))
        minimum = np.minimum(minimum,field.min(axis=1))
    return minimum,maximum


def verify(rst, cache):
    source = ROOT.parent/'1/output/latex/random_vibration/reproduction/motion'
    ref = json.loads((source/'audits/dpf_stress_unaveraged_frames.json').read_text())
    clip = np.loadtxt(source/'inputs/modal_coordinates_X_clip.csv',delimiter=',',skiprows=1)
    meta = cache_modes(rst,cache)
    if len(ref)!=480 or clip.shape!=(480,len(meta['frequencies_Hz'])+1):
        raise ValueError('Reference history dimension mismatch')
    tensor = np.load(cache/'tensors.npy',mmap_mode='r')
    minimum,maximum = extrema(tensor,clip[:,1:])
    native_max = np.array([r['maximum_Pa'] for r in ref])
    native_min = np.array([r['minimum_Pa'] for r in ref])
    errors={}
    for name,new,old in [('minimum',minimum,native_min),('maximum',maximum,native_max)]:
        errors[name+'_max_absolute_difference_Pa']=float(np.max(abs(new-old)))
        errors[name+'_max_relative_difference']=float(np.max(abs(new/old-1)))
    evidence = dict(scope='Cross-check of October X-axis signed dynamic stress reconstruction against the DPF unaveraged PCB fields',rst_sha256=meta['rst_sha256'],modes=len(tensor),frames=len(clip),element_count=meta['element_count'],element_corner_records=tensor.shape[1],peak_dynamic_von_Mises_Pa=float(maximum.max()),minimum_Pa=float(minimum.min()),differences=errors)
    print(json.dumps(evidence,indent=2),flush=True)
    if meta['element_count']!=39014 or errors['minimum_max_relative_difference']>1e-4 or errors['maximum_max_relative_difference']>1e-4:
        raise ValueError('Reconstructed stress field extrema differ from native DPF')
    (ROOT/'validation/pcb_dynamic_stress_reader.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modal_rst',type=Path)
    parser.add_argument('cache_directory',type=Path)
    parser.add_argument('--verify-october',action='store_true')
    args=parser.parse_args()
    if args.verify_october:
        verify(args.modal_rst,args.cache_directory)
    else:
        cache_modes(args.modal_rst,args.cache_directory)
