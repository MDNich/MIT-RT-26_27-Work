"""Verify the 22 shared-scale native movie pairs and compare PCB motion over the displayed time interval."""
import numpy as np

from audit_local import ROOT,read
from film_campaign import SLOTS,catalog,decode,pair_check
from film_identity import digest,verified,write_json
from report_plot import plt
from seeded_motion import FRAMES,FS
from stage_snug_fit import AUDIT


def run():
    refs=AUDIT/'film_visual_review.json'
    reviewed=read(refs)
    rows=catalog(snug_fit=True)
    assert len(rows)==22 and len(reviewed)==44
    kinds={}
    for subject in rows:
        pair_check(subject)
        for side in SLOTS:
            proof=decode(subject,side)
            mark=reviewed[subject[side]]
            assert mark['sha256']==proof['sha256'] and mark['review_sheet_sha256']==proof['sheet_sha256']
            assert mark['sidecar_sha256']==proof['sidecar_sha256'] and mark['native_reference_sha256']==proof['reference_sha256']
            assert (proof['width'],proof['height'],proof['fps'])==(3840,2160,60)
            if subject['kind']=='seeded random motion':assert proof['coordinate_method']=='native'
            if subject['kind']=='camera motion over fixed RMS':assert proof['field_method'] in (None,'native')
        kinds[subject['kind']]=kinds.get(subject['kind'],0)+1
    assert sorted(kinds.values())==[3,7,12]
    evidence={}
    for variant in ('bare','snug125_nylon','snug125_aluminium'):
        curve=ROOT/'validation/seeded_film_fields'/f'{variant}.json'
        fields=read(curve)
        assert tuple(fields['physical_interval_s'])==tuple(FRAMES[[0,-1]]/FS)
        assert set(fields['subjects'])=={r['file'].split('/')[-1][:-4] for r in rows if r['kind']=='seeded random motion'}
        peaks={}
        errors=[]
        for name,r in fields['subjects'].items():
            motion=ROOT/'validation/motion'/f"{variant}_motion_{r['axis']}.json"
            verified(motion,r['native_audit_sha256'])
            native=read(motion)
            assert native['clip_sha256']==r['native_clip_sha256'] and native['basis_rst_sha256']==r['modal_rst_sha256']
            assert native['samples']==9*FS+1 and r['frames']==len(FRAMES)
            errors.append(r['field_relative_L2'])
            if r['scope']=='pcb' and r['component']=='Z':
                assert r['units']=='mm' and r['axis'] not in peaks
                peaks[r['axis']]=r['native_scale_peak']
        assert set(peaks)==set('XYZ')
        evidence[variant]=dict(field_checks_sha256=digest(curve),peak_PCB_UZ_mm=peaks,max_field_relative_L2=max(errors))
    fig,ax=plt.subplots(figsize=(7.25,2.45),layout='constrained')
    for i,((variant,data),name,color) in enumerate(zip(evidence.items(),('Bare board','Nylon screws','Aluminium screws'),
                                                        ('#08357E','#3C78D8','#38761D'),strict=True)):
        shifts=[data['peak_PCB_UZ_mm'][a] for a in 'XYZ']
        bars=ax.bar(np.arange(3)+(i-1)*.24,shifts,width=.22,color=color,label=name)
        ax.bar_label(bars,fmt='%.3f',fontsize=8,padding=2)
    ax.set(xticks=range(3),xticklabels=['Base X','Base Y','Base Z'],ylabel='Peak PCB $|U_Z|$ [mm]',ylim=(0,.46))
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    ax.legend(loc='upper left',ncols=3,frameon=False,fontsize=8)
    fig.savefig(ROOT/'docs/figures/snug-seeded-board-travel.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(AUDIT/'movie_release.json',dict(visual_review_sha256=digest(refs),catalogue_sha256=digest(ROOT/'output/videos/snug125/README.md'),
        reviewed_movies=len(reviewed),paired_subjects=kinds,physical_time_s=(FRAMES[[0,-1]]/FS).tolist(),cases=evidence,
        scope='Peak absolute board-normal displacement in the 480 displayed frames. The plotted values use the actual '
              'displacement in the installed coordinate system before applying the movie magnification.'))


if __name__=='__main__':run()
