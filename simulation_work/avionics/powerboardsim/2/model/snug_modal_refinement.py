"""Match the two nylon mesh bases on the original board assembly and compare their integrated spectra."""
import argparse
import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from independent_psd import run as integrate_spectra
from modal_correspondence import compare as match_modes
from snug_modal_mesh import run as check_jacobians
from stage_snug_fit import AUDIT, input_record


def compare(campaign):
    staged=read(AUDIT/'modal_refinement_input.json')
    cases=[staged['reference'],staged['case']]
    branches=[case.removesuffix('_basis') for case in cases]
    spectra=[]
    paths=[]
    checks=[]
    for case,branch in zip(cases,branches,strict=True):
        archive=ROOT/'.runtime/archive'/campaign/case
        receipt=ROOT/'.runtime/receipts'/campaign/case
        status=read(receipt/'status.json')
        assert status['phase']=='solver_complete' and (receipt/'released.txt').is_file()
        model=input_record(status['parent'])
        assert model['step_sha256']==staged['step_sha256'] and model['tab_spacing_mm']==staged['tab_spacing_mm']
        installed=read(AUDIT/(status['parent']+'_installed.json'))
        assert installed['linearization_review_passed'] and installed['campaign']==campaign
        proof=read(ROOT/'validation/global'/(case+'.json'))
        assert proof['case']==case and proof['campaign']==campaign
        verified(archive/'file.rst',proof['rst_sha256'])
        verified(archive/'model.inp',staged['input_sha256'])
        check_jacobians(branch,campaign)
        checks.append(dict(case=case,preload=installed['case'],mesh_size_mm=model['size_mm'],mesh_sha256=model['mesh_sha256'],
                           installed_rst_sha256=installed['rst_sha256'],basis_rst_sha256=proof['rst_sha256']))
        path=ROOT/'validation/independent_psd'/(case+'.json')
        if not path.exists():integrate_spectra(branch,campaign)
        spectrum=read(path)
        assert spectrum['case']==case and spectrum['campaign']==campaign and spectrum['rst_sha256']==proof['rst_sha256']
        assert spectrum['baseline_5pct_screen_passed']
        spectra.append(spectrum['base_cases']);paths.append(archive/'file.rst')
        checks[-1]['spectrum_sha256']=digest(path)
    assert [c['mesh_size_mm'] for c in checks]==[2,1.5]
    modes=match_modes(*paths)
    assert [modes[k+'_rst_sha256'] for k in ('reference','candidate')]==[r['basis_rst_sha256'] for r in checks]
    response={}
    for axis in 'XYZ':
        a,b=[s[axis] for s in spectra]
        assert a['spectra_source_sha256']==b['spectra_source_sha256'] and a['scopes'].keys()==b['scopes'].keys()
        response[axis]={}
        for scope,base in a['scopes'].items():
            coarse=np.array(base['peak_directional_RMS_mm'])
            fine=np.array(b['scopes'][scope]['peak_directional_RMS_mm'])
            assert (coarse>0).all() and (fine>0).all()
            response[axis][scope]=dict(nominal_peak_XYZ_um=(1000*coarse).tolist(),fine_peak_XYZ_um=(1000*fine).tolist(),
                                      fine_minus_nominal_percent=(100*(fine/coarse-1)).tolist())
    write_json(AUDIT/'nylon_modal_mesh_comparison.json',dict(campaign=campaign,models=checks,
        native_mode_matching=modes,independent_RMS_displacements=response,
        scope='Native mode correspondence uses the identical original assembly nodes after undoing each installed pose. '
              'The PLA mesh changes. Each spectrum is independently integrated from its own native frequencies, '
              'participation and signed shapes. Each tangent fixes the contact state of its own preload.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',default='nov08_01')
    compare(parser.parse_args().campaign)
