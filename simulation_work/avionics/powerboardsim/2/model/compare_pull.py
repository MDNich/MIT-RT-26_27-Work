"""Compare two fully audited local paths at the same displacement; all forces act along PCB X."""
import argparse
import csv
import json
from pathlib import Path

from report_plot import plt
import numpy as np
from audit_local import ROOT,read,table


def series(name, *, proof_path=None):
    if proof_path is None:
        proof=read(ROOT/f'validation/local/{name}.json')
        assert proof['full_requested_path']
    else:
        proof=read(proof_path)
        assert proof_path==ROOT/'validation'/('local' if proof['full_requested_path'] else 'partial_local')/(name+'.json')
    assert proof['case']==name
    camp=proof['campaign']
    d=ROOT/f'.runtime/archive/{camp}/{name}'
    source=read(d/'local_job.json')['source']
    t0=read(ROOT/f'.runtime/local_inputs/{source}/config.json')['pull_start_time']
    eq=table(ROOT/f'.runtime/post/{camp}/{name}/whole_fixture_balance.csv')
    native=table(d/'history.csv')
    sets=eq['native_set'].astype(int)
    assert np.array_equal(native['set'][sets-1],sets)
    assert np.allclose(native['fx_N'][sets-1],eq['cell_fx_N'],rtol=1e-6,atol=1e-5)
    rows=[]
    for i in np.flatnonzero(eq['time']>=t0-1.e-7):
        er=eq[i];hi=native[sets[i]-1]
        cell=er['cell_fx_N'];resid=er['force_N_x']
        # RF of a fixed mounting point is its force on this isolated fixture.
        screws=-er['screw_support_N_x'] if 'screw_support_N_x' in eq.dtype.names else 0.
        neighbor=-er['neighbor_support_N_x'] if 'neighbor_support_N_x' in eq.dtype.names else 0.
        strip=cell-screws-neighbor-resid
        rows.append(dict(case=name,set=int(sets[i]),ux_mm=float(er['ux_mm']),cell_force_N=float(cell),
                         screw_path_N=float(screws),neighbour_path_N=float(neighbor),clamp_path_N=float(strip),
                         equilibrium_residual_N=float(resid),nickel_peak_plastic_strain=float(hi['max_eppl'])))
    assert np.all(np.diff([abs(r['ux_mm']) for r in rows])>0)
    return proof,rows


def compare(name,bare):
    new,case_rows=series(name);ref,base_rows=series(bare)
    end,base=case_rows[-1],base_rows[-1]
    assert new['campaign']==ref['campaign'] and new['source']==ref['source']
    assert np.isclose(end['ux_mm'],base['ux_mm'],rtol=0,atol=1e-8)
    out=ROOT/'validation/pulls';out.mkdir(exist_ok=True)
    with (out/(name+'.csv')).open('w',newline='') as io:
        w=csv.DictWriter(io,fieldnames=base,lineterminator='\n');w.writeheader();w.writerows(base_rows+case_rows)
    summary=dict(cased_case=name,baseline_case=bare,cased_rst_sha256=new['rst_sha256'],bare_rst_sha256=ref['rst_sha256'],
                 terminal_displacement_mm=end['ux_mm'],bare=base,cased=end,
                 force_ratio=end['cell_force_N']/base['cell_force_N'],
                 nickel_peak_plastic_strain_ratio=end['nickel_peak_plastic_strain']/base['nickel_peak_plastic_strain'],
                 case_path_fraction=(end['screw_path_N']+end['neighbour_path_N'])/end['cell_force_N'],
                 active_contact=new['pair_861'],
                 scope='Local fixture with fixed screw tops and fixed adjacent cells and washers; case does not contact nickel strips directly. Equal-displacement comparison. No rupture or vibration claim.')
    # Interpolate only on the first recorded crossing; retain the native travel
    # bracket so the inference is distinguishable from an exact native endpoint.
    direction=np.sign(base['cell_force_N'])
    ff=np.array([r['cell_force_N'] for r in case_rows])*direction
    xx=np.array([r['ux_mm'] for r in case_rows])
    crossing=np.flatnonzero((ff[1:]>=abs(base['cell_force_N']))&(ff[:-1]<abs(base['cell_force_N'])))
    if len(crossing):
        j=crossing[0]
        travel=np.interp(abs(base['cell_force_N']),ff[j:j+2],xx[j:j+2])
        summary['equal_bare_terminal_force']=dict(target_N=base['cell_force_N'],first_cased_native_travel_bracket_mm=xx[j:j+2].tolist(),
            interpolated_cased_travel_mm=float(travel),bare_travel_mm=base['ux_mm'])
    (out/(name+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.75),layout='constrained')
    for rows,label,color in [(base_rows,'Bare','#08357E'),(case_rows,'Raised case','#38761D')]:
        x=[r['ux_mm'] for r in rows]
        for ax,var,mult in zip(axes,['cell_force_N','nickel_peak_plastic_strain'],[1,100]):
            ax.plot(x,[r[var]*mult for r in rows],'.-',ms=3,lw=1.4,color=color,label=label)
    axes[0].plot([r['ux_mm'] for r in case_rows],[r['screw_path_N']+r['neighbour_path_N'] for r in case_rows],
                 '--',lw=1.3,color='#7A0101',label='Via case supports')
    for ax,ylabel in zip(axes,['Lateral force [N]','Peak nickel plastic strain [\\%]']):
        ax.set(xlabel='Edge-cell travel [mm]',ylabel=ylabel);ax.grid(alpha=.18);ax.legend(fontsize=7,frameon=False)
        bracket=new['pair_861']['contact_travel_bracket_mm']
        if bracket:ax.axvspan(*sorted(bracket),color='#3C78D8',alpha=.13,lw=0)
    fig.savefig(ROOT/f'docs/figures/{name}.pdf');plt.close(fig)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('name');p.add_argument('--bare',default='bare_lateral_friction_locked')
    a=p.parse_args();compare(a.name,a.bare)
