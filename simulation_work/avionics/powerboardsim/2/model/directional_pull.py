"""Compare the two signed October bilinear pulls on the bare board and both raised mounts."""
import numpy as np

from audit_local import ROOT, read
from compare_pull import series
from film_identity import digest, verified, write_json
from report_plot import plt


def verify_drive_pair(forward, reverse, campaign):
    decks = []
    fingerprints = {}
    for case in (forward, reverse):
        archive = ROOT/'.runtime/archive'/campaign/case
        receipt = read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
        entry, = [f for f in receipt['files'] if f['name'] == 'model.inp']
        verified(archive/'model.inp', entry['sha256'])
        fingerprints[case] = entry['sha256']
        decks.append((archive/'model.inp').read_text().splitlines())
    differences = [(a,b) for a,b in zip(*decks,strict=True) if a != b]
    # Four identical real constants use a different decimal spelling in the October input.
    equivalent = [(f'R,{i},,,.1,.01,,.2', f'R,{i},,,0.1,.01,,.2') for i in range(1,5)]
    assert differences == equivalent + [('D,2481,UX,0.5', 'D,2481,UX,-0.5')]
    return fingerprints


def compare():
    outcomes = {}
    curves = {}
    source_root = ROOT/'validation'
    for direction, suffix in ((1, ''), (-1, '_minus')):
        source = 'lateral_friction_locked' + suffix
        bare = 'bare_' + source
        for label, material in (('Bare', None), ('Nylon', 'nylon'), ('Aluminium', 'aluminium')):
            case = bare if material is None else f'stand3_{material}_{source}_pin1'
            proof, rows = series(case)
            assert proof['source'] == source and proof['full_requested_path']
            assert np.isclose(rows[-1]['ux_mm'], direction * .5, rtol=0, atol=1e-9)
            assert proof['max_relative_lateral_imbalance'] < .001
            x = np.array([r['ux_mm']*direction for r in rows])
            assert np.all(np.diff(x) > 0) and abs(x[0]) < 1e-6
            curve = np.array([r['cell_force_N']*direction for r in rows])
            assert np.all(curve[1:] > 0)
            first_limit = len(rows)
            result = dict(case=case, rst_sha256=proof['rst_sha256'], endpoint=rows[-1])
            if material:
                strength = read(source_root/'pull_material'/f'{case}.json')
                contact_file = source_root/'pulls'/f'{case}_contact.csv'
                contact = read(contact_file.with_suffix('.json'))
                assert strength['rst_sha256'] == contact['rst_sha256'] == proof['rst_sha256']
                contacts = np.genfromtxt(contact_file, delimiter=',', names=True,
                                         usecols=('native_set','pair','max_closed_corner_penetration_mm'))
                assert np.isfinite(contacts.view(float)).all()
                assert set(contacts['pair']) == {861, 862}
                assert np.isclose(np.max(contacts['max_closed_corner_penetration_mm']), contact['max_closed_corner_penetration_mm'])
                limits = {v['native_set'] for k,v in strength['first_reference_crossings'].items() if k.startswith('all_')}
                limits.update(contacts['native_set'][contacts['max_closed_corner_penetration_mm'] > .05].astype(int))
                if limits:
                    first_limit = next(i for i,r in enumerate(rows) if r['set'] >= min(limits))
                at_end = strength['history'][-1]
                assert at_end['native_set'] == rows[-1]['set']
                result.update(contact_readback_sha256=digest(contact_file),
                              first_native_closure_signed_mm=proof['pair_861']['contact_travel_bracket_mm'],
                              last_travel_within_material_and_contact_screens_mm=rows[first_limit-1]['ux_mm'],
                              max_closed_penetration_mm=contact['max_closed_corner_penetration_mm'],
                              endpoint_PLA_in_plane_MPa=at_end['all_in_plane_tension_MPa'],
                              endpoint_PLA_layer_normal_MPa=at_end['all_layer_tension_MPa'])
            outcomes[case] = result
            curves[(direction,label)] = (x,curve,rows,first_limit)
    deck_hashes = {}
    for (direction, label), (_, _, rows, _) in curves.items():
        if direction == 1:
            forward = rows[-1]['case']
            reverse = curves[-1,label][2][-1]['case']
            campaign = read(source_root/'local'/f'{forward}.json')['campaign']
            assert campaign == read(source_root/'local'/f'{reverse}.json')['campaign']
            deck_hashes.update(verify_drive_pair(forward, reverse, campaign))
    shortest = min(x[limit-1] for x,_,_,limit in curves.values())
    # Use the largest saved travel shared by all six paths within the governing screens.
    common = set.intersection(*[{round(float(t),7) for t in x[:limit] if t<=shortest+1e-8}
                                for x,_,_,limit in curves.values()])
    station = max(common)
    assert station > 0
    for x,_,rows,_ in curves.values():
        i, = np.flatnonzero(np.isclose(x,station,rtol=0,atol=1e-7))
        outcomes[rows[i]['case']]['shared_station'] = rows[i]

    fig, axes = plt.subplots(1,2,figsize=(7.4,3.25),layout='constrained', sharex=True, sharey=True)
    for direction, ax, title in zip((1,-1),axes,('Positive X pull','Negative X pull'),strict=True):
        for label, colour in (('Bare','#08357E'),('Nylon','#3C78D8'),('Aluminium','#38761D')):
            x,y,_,limit = curves[(direction,label)]
            ax.plot(x[:limit],y[:limit],'.-',ms=3,lw=1.5,color=colour,label=label)
            if limit < len(x):
                ax.plot(x[limit-1:],y[limit-1:],'.--',ms=3,lw=1.4,color=colour)
        ax.set(xlabel='Absolute cell travel [mm]',title=title,xlim=(0,.51))
        ax.grid(alpha=.18)
    axes[0].set_ylabel('Applied force magnitude [N]')
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles,names,loc='outside lower center', ncol=3,frameon=False)
    fig.savefig(ROOT/'docs/figures/directional-pull.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write_json(source_root/'pulls/directional.json',dict(common_travel_magnitude_mm=station, cases=outcomes, solved_input_sha256=deck_hashes,
               scope='Native displacement-controlled bilinear nickel fixtures at the 3 mm stand-off. The dashed curves extend beyond a contact or printed-PLA reference.'))


if __name__=='__main__':
    compare()
