"""Audit the snug assembly state before extracting a tangent basis about bolt lock."""
import sys
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from installation_material import run as audit_material
from stage_snug_fit import AUDIT,input_record


def review(case, campaign):
    entry=input_record(case)
    proof_path=ROOT/'validation/global'/f'{case}.json'
    proof=read(proof_path)
    assert case.endswith('_static') and proof['campaign']==campaign and proof['case']==case
    archive=ROOT/'.runtime/archive'/campaign/case
    verified(archive/'model.inp',entry['input_sha256'])
    audit_material(case,campaign)
    material=read(ROOT/'validation/installation_material'/f'{case}.json')
    assert material['rst_sha256']==proof['rst_sha256']
    shape=read(AUDIT/f"mesh_{entry['size_mm']}.json")
    assert material['case_tets']==shape['tetrahedra']
    states=proof['contact_history_native_RST']
    assert len(states)==len(material['history']) and all(r['n_contact']>0 for r in states)
    peak_pen_mm=max(r['loaded_corner_pen_max'] for r in states)*1000
    assert np.isfinite(peak_pen_mm) and peak_pen_mm>=0
    bolts=proof['locked_bolt_reactions_N']
    assert len(bolts)==6 and max(abs(x-750) for x in bolts)<1
    surface=read(AUDIT/entry.get('surface_closure_file','cell_surface_closure.json'))
    init=[r for r in surface['rows'] if r['mesh_mm']==entry['size_mm'] and r['subdivision']==3]
    assert len(init)==3
    # Same local hardware-penetration and printed-material screens used for the installation study.
    # A tangent extraction represents the computed state, even if contact later changes under vibration.
    passed=not material['first_reference_crossings'] and peak_pen_mm<=.05 and not any(r['intersects_at_1p25'] for r in init)
    write_json(AUDIT/f'{case}_installed.json',dict(case=case,campaign=campaign,rst_sha256=proof['rst_sha256'],
               material_readback_sha256=digest(ROOT/'validation/installation_material'/f'{case}.json'),
               locked_bolt_forces_N=bolts,initial_cell_geometry=init,contact_history=states,
               peak_loaded_corner_penetration_mm=peak_pen_mm,first_reference_crossings=material['first_reference_crossings'],
               linearization_review_passed=passed,scope='Mesh-specific equilibrium for the tangent model. Check contact changes during subsequent dynamic response.'))


if __name__=='__main__':
    review(*sys.argv[1:])
