"""Compare unaveraged PCB stresses at common physical times in the original base-X movie."""
import argparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read
from film_identity import digest,verified,write_json
from pcb_dynamic_stress import cache_modes,equivalent,extrema
from seeded_motion import FS,FRAMES,integrate,participation


def run(campaign):
    cases=['bare','stand3_nylon','stand3_aluminium']
    curves={}
    reference=None
    time=FRAMES/FS
    for variant in cases:
        key=variant+'_basis'
        basis=read(ROOT/'validation/global'/(key+'.json'))
        folder=ROOT/'.runtime/archive'/campaign/key
        path=folder/'file.rst'
        assert basis['case']==key and basis['campaign']==campaign
        verified(path,basis['rst_sha256'])
        ledger=read(ROOT/'.runtime/receipts'/campaign/key/'archived.json')
        log=folder/'solve.out'
        verified(log,next(f['sha256'] for f in ledger['files'] if f['name']=='solve.out'))
        cache=ROOT/'.runtime/post'/campaign/(variant+'_films')/'pcb_stress'
        record=cache_modes(path,cache)
        assert record['rst_sha256']==basis['rst_sha256']
        freq=np.array(record['frequencies_Hz'])
        assert np.array_equal(freq,basis['frequencies_Hz'])
        labels=np.load(cache/'locations.npz')
        matches=(np.repeat(labels['element'],labels['counts']),labels['node'])
        if reference is None:
            reference=matches
        else:
            assert all(np.array_equal(a,b) for a,b in zip(matches,reference,strict=True))
        tensor=np.load(cache/'tensors.npy',mmap_mode='r')
        dest=ROOT/'validation/motion'/f'{variant}_motion_X.json'
        native_reference=None
        if dest.is_file():
            proof=read(dest)
            assert proof['campaign']==campaign and proof['basis_rst_sha256']==basis['rst_sha256']
            clip=ROOT/f'.runtime/post/{campaign}/{variant}_motion_X/coordinates.npz'
            verified(clip,proof['clip_sha256'])
            with np.load(clip) as sample:
                q=sample['coordinates']
                assert np.array_equal(time,sample['time_s']) and np.array_equal(freq,sample['frequencies_Hz'])
            native_reference=proof['clip_sha256']
        else:
            t,q,_=integrate(freq,participation(log.read_text(errors='replace'),'X'),'X',FRAMES)
            assert np.array_equal(t,time)
        assert q.shape==(480,len(freq))
        low,high=extrema(tensor,q)
        peak=int(high.argmax())
        field=equivalent((q[peak]@tensor.reshape(len(freq),-1)).reshape(-1,6))
        ix=int(field.argmax())
        assert np.isclose(field[ix],high[peak],rtol=1e-12)
        record=dict(variant=variant,basis_sha256=basis['rst_sha256'],mode_count=len(freq),
                    coordinate_method='Native MCF' if native_reference else 'Independent integration',
                    native_clip_sha256=native_reference,modal_tensor_sha256=digest(cache/'tensors.npy'),
                    corner_labels_sha256=digest(cache/'locations.npz'),element_count=len(labels['element']),corners=len(field),
                    peak_frame=peak+1,peak_time_s=float(time[peak]),clip_peak_MPa=float(high[peak]*1e-6),
                    peak_element=int(matches[0][ix]),peak_node=int(matches[1][ix]),
                    frame_maximum_MPa=(high*1e-6).tolist(),frame_minimum_MPa=(low*1e-6).tolist())
        if variant=='bare':
            old=ROOT.parent/'1/output/latex/random_vibration/reproduction/motion/audits/dpf_stress_unaveraged_frames.json'
            prior=read(old)
            assert [a['frame'] for a in prior]==list(range(1,481))
            ref=np.array([a['maximum_Pa'] for a in prior])
            err=float(np.max(abs(high/ref-1)))
            assert err<.001
            record.update(October_DPF_sha256=digest(old),maximum_frame_peak_relative_error=err)
        curves[variant]=record
        print(variant,record['clip_peak_MPa'],peak+1,record['peak_node'],flush=True)
    write_json(ROOT/'validation/seeded_pcb_stress_comparison.json',dict(campaign=campaign,frames=len(time),
        physical_time_s=[float(time[0]),float(time[-1])],frame_spacing_s=float(4/FS),cases=curves,
        scope='Maximum over unaveraged PCB element corners at each stored movie frame. Native signed modal stress '
              'components are summed before evaluating von Mises. The film shows the dynamic increment about bolt preload.'))
    fig,ax=plt.subplots(figsize=(7.5,2.4),layout='constrained')
    ms=1000*(time-time[0])
    for (name,data),label,col,ls in zip(curves.items(),('Bare','3 mm / nylon','3 mm / aluminium'),
                                       ('#08357E','#3C78D8','#38761D'),('-','--','-.'),strict=True):
        ax.plot(ms,data['frame_maximum_MPa'],color=col,ls=ls,lw=1.35,label=label)
        i=data['peak_frame']-1
        ax.plot(ms[i],data['clip_peak_MPa'],'o',color=col,ms=3.5)
    ax.legend(ncols=3,frameon=False,fontsize=8,loc='upper left',bbox_to_anchor=(0,1.16))
    ax.set(xlim=(0,ms[-1]),ylim=(0,None),xlabel='Time from the first movie frame [ms]',ylabel='Peak PCB stress [MPa]')
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='y',alpha=.17)
    fig.savefig(ROOT/'docs/figures/raised-seeded-pcb-stress.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign',nargs='?',default='nov08_01')
    run(parser.parse_args().campaign)
