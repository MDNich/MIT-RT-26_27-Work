"""Check the retained translational mass by axis; keep rank-ordered spectra separate from shape correspondence."""
import json
import re
import sys
import numpy as np
from film_identity import ROOT, verified, digest, write_json


def audit(case,campaign):
    folder=ROOT/'.runtime/archive'/campaign/case
    receipt=ROOT/'.runtime/receipts'/campaign/case
    def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
    ledger=read(receipt/'archived.json');proof=read(ROOT/'validation/global'/f'{case}.json')
    assert case.endswith('_basis') and proof['case']==ledger['case']==case and proof['campaign']==ledger['campaign']==campaign
    checksums={v['name']:v['sha256'] for v in ledger['files']}
    verified(folder/'solve.out',checksums['solve.out']);assert checksums['file.rst']==proof['rst_sha256']
    txt=(folder/'solve.out').read_text(errors='replace')
    freq=np.asarray(proof['frequencies_Hz']);mass=float(re.search(r'^\s*TOTAL MASS\s*=\s*(\S+)',txt,re.M)[1])
    ref=ROOT.parent/'1/output/latex/random_vibration/reproduction/native/modal_basis'
    baseline=case=='bare_basis';base={}
    if baseline:
        old=read(ref/'audit.json')
        assert digest(ref/'solve.out')==old['solve_sha256']
        f0=np.loadtxt(ref/'frequencies.csv',delimiter=',',skiprows=1)[:,1]
        assert len(freq)==old['count']==len(f0)
        base['max_relative_frequency_error']=float(np.max(abs(freq/f0-1)))
        assert base['max_relative_frequency_error']<1.e-6
        assert proof['warnings']==old['warning_count']
        base['warnings_in_each_listing']=proof['warnings']
    out={}
    for axis in 'XYZ':
        m=re.search(r'PARTICIPATION FACTOR CALCULATION \*+\s*'+axis+r'\s+DIRECTION(.*?)^\s*sum\s+(\S+)\s+(\S+)',txt,re.S|re.M|re.I)
        assert m
        a=np.array([[float(v) for v in line.split()] for line in m[1].splitlines() if line.split() and line.split()[0].isdigit()])
        assert a.shape==(len(freq),8) and np.array_equal(a[:,0],np.arange(len(freq))+1)
        assert np.allclose(a[:,1],freq,atol=.006,rtol=2e-6)
        assert np.allclose(a[:,3]**2,a[:,5],rtol=1.1e-4,atol=1e-13)
        assert mass>0 and np.allclose(a[:,5]/mass,a[:,7],rtol=1e-4,atol=1e-9)
        eff=float(a[:,7].sum())
        assert abs(float(m[2])-a[:,5].sum())<5e-6 and abs(float(m[3])-eff)<5e-6
        # The cumulative extracted-mass fraction ends at one even if some real mass is omitted.
        assert abs(a[-1,6]-1)<1e-6 and 0<eff<1.0001
        peak=int(np.argmax(a[:,7]))
        data=dict(effective_mass_kg=float(a[:,5].sum()),fraction_of_total=eff,
                  fraction_of_total_with_mode_frequencies_20_to_2000_Hz=float(a[(freq>=20)&(freq<=2000),7].sum()),
                  largest_mode_rank=peak+1,largest_mode_Hz=float(freq[peak]),largest_mode_mass_fraction=float(a[peak,7]))
        if baseline:
            hist=np.genfromtxt(ref/f'participation_{axis}.csv',delimiter=',',names=True)
            maxerr=float(np.max(abs(hist['fraction_of_total_mass']-a[:,7])))
            assert abs(eff-old['effective_mass_fraction'][axis])<5e-6 and maxerr<5e-6
            data['max_absolute_per_mode_mass_fraction_change_from_October']=maxerr
        out[axis]=data
    dest=ROOT/'validation/basis_mass'/f'{case}.json'
    rec=dict(case=case,campaign=campaign,mass_kg=mass,retained_modes=len(freq),span_Hz=[float(freq[0]),float(freq[-1])],
             within_input_band_modes=int(np.count_nonzero((freq>=20)&(freq<=2000))),axes=out,
             native_result_sha256=proof['rst_sha256'],native_listing_sha256=checksums['solve.out'],october_repeat=base,
             scope='Translational participation in the retained eigenbasis, not a forced vibration amplitude. Modes above the input band can still contribute to response.')
    write_json(dest,rec)
    print(case,len(freq),'modes;',','.join(f'{a}: {v["fraction_of_total"]:.5f}' for a,v in out.items()))
    return rec

if __name__=='__main__':audit(*sys.argv[1:])
