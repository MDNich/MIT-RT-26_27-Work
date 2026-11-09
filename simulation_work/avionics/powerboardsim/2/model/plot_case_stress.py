"""Illustrate the stress normal to the print layers at the native corner with the highest base-X RMS."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from audit_local import ROOT,read
from film_identity import verified


def draw():
    case='stand3_nylon_psd_X_private1'
    data=read(ROOT/'validation/pla_stress'/f'{case}.json')
    wave=data['independent_signed_waveform']
    path=ROOT/'.runtime/post'/data['campaign']/case/'PLA_critical_history.npz'
    verified(path,wave['cache_sha256'])
    with np.load(path) as f:y=f['signed_stress_MPa']
    t=np.arange(len(y))/wave['sample_rate_Hz'];assert t[-1]==9
    # Show actual sample extrema in each time window, retaining the global peaks.
    groups=np.array_split(np.arange(len(y)),450)
    x=np.array([t[g].mean() for g in groups])
    low=np.array([y[g].min() for g in groups]);high=np.array([y[g].max() for g in groups])
    fig,(ax,ar)=plt.subplots(1,2,figsize=(7.5,2.55),width_ratios=[1.6,1],layout='constrained')
    ax.fill_between(x,low,high,color='#3c78d8',alpha=.85,linewidth=.25)
    ax.axhline(40.5,color='#7A0101',ls='--',lw=1.1,label='Printed coupon tension, 40.5 MPa')
    ax.set_xlabel('Realization time [s]');ax.set_ylabel('Signed Z stress [MPa]')
    ax.set_xlim(0,9);ax.set_ylim(-70,85);ax.legend(loc='upper left',frameon=False,fontsize=7.5)
    ax.set_title('Critical tab corner',fontsize=10)
    rows=data['bearing_proximity'];xx=np.arange(len(rows))
    bars=ar.bar(xx,[r['Z_RMS_MPa'] for r in rows],color=['#08357E','#3C78D8','#3C78D8','#3C78D8'])
    ar.bar_label(bars,fmt='%.2f',fontsize=8,padding=2)
    ar.set_xticks(xx,[str(r['minimum_distance_from_bearing_nodes_mm']) for r in rows]);ar.set_ylim(0,21)
    ar.set_ylabel('Peak Z stress [MPa RMS]')
    ar.set_xlabel('Minimum distance from\nbearing nodes [mm]')
    ar.set_title('Native base-X spectrum',fontsize=10)
    for a in (ax,ar):a.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'docs/figures/raised-nylon-layer-stress.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


if __name__=='__main__':draw()
