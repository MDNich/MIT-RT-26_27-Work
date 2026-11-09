"""Open a combined MAPDL result with empty element slots without passing zero geometry pointers to Cython."""
import numpy as np
from ansys.mapdl.reader.rst import Result,_binary_reader
from ansys.mapdl.reader.mesh import Mesh


class CombinedResult(Result):
    def _store_mesh(self,parse_vtk=True):
        h=self._geometry_header
        p=int(h['ptrEID']);idx=self.read_record(p).view(np.int64)
        if (idx>0).all() and np.all(np.diff(idx)>0):
            self._occupied=None
            return super()._store_mesh(parse_vtk)
        self._occupied=keep=idx!=0
        assert idx.shape==(h['nelm'],) and np.array_equal(keep,self._eeqv!=0)
        assert np.all(idx[keep]>0) and np.all(np.diff(idx[keep])>0)
        expected=self._eeqv[keep]
        assert np.unique(expected).size==expected.size
        nn=int(h['nnod']);nnum=np.empty(nn,np.int32);nodes=np.empty((nn,6))
        _binary_reader.load_nodes(self.filename,h['ptrLOC'],nn,nodes,nnum)
        assert np.all(np.diff(nnum)>0) and np.isfinite(nodes).all()
        self._c_systems=self.parse_coordinate_system()
        # Read each valid record with recorded length instead of inferring lengths across holes.
        # Preserve equation order, including the independent solution-table mask below.
        data=[self.read_record(p+int(offset)) for offset in idx[keep]]
        assert all(10<len(d)<256 and d[8]==n for d,n in zip(data,expected,strict=True))
        off=np.asarray(np.r_[0,np.cumsum([len(d) for d in data])],dtype=np.int32)
        nc,ec=self._read_components()
        self._mesh=Mesh(nnum,nodes,np.concatenate(data),off,self._element_table['ekey'],node_comps=nc,elem_comps=ec)
        self._eeqv=expected
        self._sidx_elem=np.argsort(expected)
        assert np.array_equal(self._mesh.enum,expected)
        if parse_vtk:
            self.quadgrid=self._mesh._parse_vtk(null_unallowed=True,fix_midside=False)
            self.grid=self.quadgrid.linear_copy()
        else:self.quadgrid=self.grid=None
        self._insolution=np.isin(nnum,self._resultheader['neqv'],assume_unique=True)

    def sparse_window(self,rnum,solution_type='NSL'):
        import struct
        k=int(self.parse_step_substep(rnum))%self.nsets
        h=self._result_solution_header(k)
        ptr=int(self._resultheader['rpointers'][k])+int(h['ptr'+solution_type])
        with open(self.filename,'rb') as f:
            f.seek(4*ptr+4);flags=struct.unpack('<I',f.read(4))[0]
        return (flags & 0x18000000)==0x18000000

    def _nodal_solution_result(self,rnum,solution_type,in_nodal_coord_sys=False,nodes=None):
        from pathlib import Path
        k=int(self.parse_step_substep(rnum))%self.nsets
        # The old reader cannot decode these combined sparse-window records.
        if self.sparse_window(k,solution_type):
            if solution_type!='NSL' or in_nodal_coord_sys or nodes is not None:
                raise ValueError('DPF fallback provides only global translations for the full field')
            path=Path(self.filename).resolve()
            assert path.parent.parent.parent.name=='archive' and path.name=='file.rst'
            from dpf_readback import export
            dest=export(path.parent.name,path.parent.parent.name,[k+1])
            stem=dest/f'set_{k+1:04d}'
            ids=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
            order=np.argsort(ids)
            return ids[order],u[order]
        return super()._nodal_solution_result(rnum,solution_type,in_nodal_coord_sys,nodes)

    def _element_solution_header(self,rnum):
        ptr,types,offset=super()._element_solution_header(rnum)
        if self._occupied is not None:
            assert ptr.shape==self._occupied.shape
            # A PSD combination may allocate an empty element-result index record even for
            # an unused mesh slot. Only discard a slot after verifying that it has no data.
            for location in ptr[~self._occupied]:
                if location:
                    record=self.read_record(int(offset)+int(location))
                    if len(record)!=27 or np.any(record):
                        raise ValueError('Element result exists without a matching geometry record')
            ptr=ptr[self._occupied]
        return ptr,types,offset


def read_rst(path,**kwargs):
    return CombinedResult(path,**kwargs)
