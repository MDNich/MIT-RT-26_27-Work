"""Prepare an independent MAPDL model and face map. Never calls SOLVE."""
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parent
FACES = ((1, 0, 3, 2), (0, 1, 5, 4), (1, 2, 6, 5),
         (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def triangle(a, b, c):
    v = cross([b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)])
    return math.sqrt(sum(x*x for x in v))/2


def parse_mesh(text):
    nodes, elements = {}, {}
    mat = typ = 0
    lines = iter(text.splitlines())
    for line in lines:
        if line.lower().startswith('mat,'):
            mat = int(re.search(r'MAT,(\d+)', line, re.I)[1])
            typ = int(re.search(r'TYPE,(\d+)', line, re.I)[1])
        if line.lower().startswith('nblock,'):
            next(lines)
            for row in lines:
                if row.strip() == '-1': break
                parts = row.split()
                nodes[int(parts[0])] = [float(x) for x in parts[1:4]]
        if line.lower().startswith('eblock,'):
            next(lines)
            for row in lines:
                if row.strip() == '-1': break
                parts = [int(row[i:i+9]) for i in range(0, len(row), 9) if row[i:i+9].strip()]
                if typ in (1, 2, 3, 4):
                    assert len(parts) == 9, (typ, parts)
                    elements[parts[0]] = dict(mat=mat, typ=typ, nodes=parts[1:])
    return nodes, elements


def radial_faces(nodes, elements, cfg):
    g = cfg['geometry']
    dr = g['phe0_thickness_m']/g['radial_rows']
    rows = [[] for _ in range(g['radial_rows'])]
    outer = []
    for eid, e in elements.items():
        radii = [math.hypot(nodes[n][0], nodes[n][2]) for n in e['nodes']]
        rlo, rhi = min(radii), max(radii)
        ylo = min(nodes[n][1] for n in e['nodes'])
        yhi = max(nodes[n][1] for n in e['nodes'])
        angles = [math.atan2(nodes[n][0], nodes[n][2]) for n in e['nodes']]
        # Exact volume of the straight-sided swept hex, matching the FE mesh.
        e['volume'] = .5*(rhi*rhi-rlo*rlo)*math.sin(max(angles)-min(angles))*(yhi-ylo)
        if e['mat'] not in (1, 4): continue
        target = rlo if e['mat'] == 1 else g['outer_radius_m']
        for face, indices in enumerate(FACES, 1):
            ids = [e['nodes'][i] for i in indices]
            if max(abs(math.hypot(nodes[n][0], nodes[n][2])-target) for n in ids) > 2e-9:
                continue
            xyz = [nodes[n] for n in ids]
            area = triangle(xyz[0],xyz[1],xyz[2])+triangle(xyz[0],xyz[2],xyz[3])
            entry = dict(element=eid, face=face, nodes=ids, area=area)
            if e['mat'] == 1:
                row = round((rlo-g['inner_radius_m'])/dr)
                assert 0 <= row < len(rows)
                entry['volume'] = e['volume']
                rows[row].append(entry)
            else:
                outer.append(entry)
    assert len(nodes) == 54540 and len(elements) == 35200
    assert all(len(row) == 200 for row in rows)
    assert len(outer) == 200
    for i, row in enumerate(rows):
        expected = math.radians(g['angle_deg'])*(g['inner_radius_m']+i*dr)*g['length_m']
        assert abs(sum(f['area'] for f in row)/expected-1) < 1e-6
        assert len(set(n for f in row for n in f['nodes'])) == 303
    return dict(nodes=nodes, elements=elements, rows=rows, outer=outer)


def material_input(cfg):
    m=cfg['material']
    table=[(22.,.25,.30,900,800),(26.85,.25,.30,900,800),
           (326.85,.32,.35,1100,900),(626.85,.36,.40,1300,1000),
           (776.85,.36,.44,1300,1250),(926.85,.36,.49,1300,1550),
           (1226.85,.36,.68,1300,1950),(1426.85,.36,.81,1300,2060),
           (1926.85,.36,1.24,1300,2085),(2476.85,.36,1.73,1300,2090)]
    out=['! Iteration 4: fixed REFERENCE densities; fixed mesh, no thermal expansion.',
         '! Avoids temperature-induced mass changes unaccounted for in gas generation.',
         'TBDELE,USER,1','TBDELE,STATE,1','TB,USER,1,10,15,THERM']
    for T,kv,kc,cpv,cpc in table:
        out += [f'TBTEMP,{T}',f'TBDATA,1,{kv},{kc},{cpv},{cpc},{m["virgin_reference_density_kg_m3"]},{m["char_reference_density_kg_m3"]}',
                f'TBDATA,7,333,64081,1,{m["pyrolysis_enthalpy_J_kg"]},273.15,1600',
                'TBDATA,13,300,1,1']
    out += ['TB,STATE,1,,5','TBDATA,1,0,0,0,0,0']
    return '\n'.join(out)+'\n'


def export_macro(mesh):
    nmax=max(map(int,mesh['nodes'])); emax=max(map(int,mesh['elements']))
    # Arrays are deleted/recreated after each restart; no state hidden in APDL.
    out=['FINISH','/POST1','SET,LAST','ALLSEL,ALL',
         '*GET,S4_TIME,ACTIVE,0,SET,TIME','*CFOPEN,observed_time,txt',
         '*VWRITE,S4_TIME','(E24.16)','*CFCLOSE']
    for name,length in [('S4_N',nmax),('S4_T',nmax),('S4_M',nmax),('S4_E',emax)]:
        out += [f'*DEL,{name}',f'*DIM,{name},ARRAY,{length}']
    out += ['*VFILL,S4_N(1),RAMP,1,1','*VGET,S4_T(1),NODE,1,TEMP',
            '*VGET,S4_M(1),NODE,1,NSEL','*CFOPEN,node_temperatures,txt',
            '*VMASK,S4_M(1)','*VWRITE,S4_N(1),S4_T(1)','(F10.0,1X,E24.16)','*CFCLOSE',
            '*VFILL,S4_E(1),RAMP,1,1','ESEL,S,TYPE,,1,4','ESEL,R,LIVE','ETABLE,ERAS']
    fields=[('ALP','SVAR,1'),('GAS','SVAR,3'),('GSEN','SVAR,5'),('QZ','TF,Z'),
            ('CAP','NMISC,38'),('GEN','NMISC,39'),('CONV','NMISC,40'),('HFX','NMISC,41'),('RAD','NMISC,42')]
    # SVARs exist only on phe0; fill zeros on the other materials explicitly.
    for label,item in fields:
        out += [f'*DEL,S4_{label}',f'*DIM,S4_{label},ARRAY,{emax}']
        if item.startswith('SVAR'):
            out += ['ESEL,S,TYPE,,1','ESEL,R,LIVE']
        else: out += ['ESEL,S,TYPE,,1,4','ESEL,R,LIVE']
        out += [f'ETABLE,{label},{item}',f'*VGET,S4_{label}(1),ELEM,1,ETAB,{label}']
    out += [f'*DEL,S4_EM',f'*DIM,S4_EM,ARRAY,{emax}',
            'ESEL,S,TYPE,,1,4','ESEL,R,LIVE','*VGET,S4_EM(1),ELEM,1,ESEL',
            '*CFOPEN,element_fields,txt','*VMASK,S4_EM(1)',
            '*VWRITE,S4_E(1),S4_ALP(1),S4_GAS(1),S4_GSEN(1),S4_QZ(1)',
            '(F10.0,4(1X,E24.16))','*CFCLOSE',
            '*CFOPEN,energy_fields,txt','*VMASK,S4_EM(1)',
            '*VWRITE,S4_E(1),S4_CAP(1),S4_GEN(1),S4_CONV(1),S4_HFX(1),S4_RAD(1)',
            '(F10.0,5(1X,E22.14))','*CFCLOSE',
            'ALLSEL,ALL','FINISH']
    return '\n'.join(out)+'\n'


def main():
    if (ROOT/'state.json').exists():
        raise RuntimeError('Started calculation preserved: build a new sibling iteration instead.')
    cfg=json.loads((ROOT/'config.json').read_text())
    text=(ROOT/'source/simulation3_executed_ds.dat').read_text()
    nodes,elements=parse_mesh(text)
    mesh=radial_faces(nodes,elements,cfg)
    (ROOT/'mesh_map.json').write_text(json.dumps(mesh,separators=(',',':')))
    base=text.split('/com,*********** Create "Convection 2"')[0]
    start=base.index('! Native Fortran UserMatTh')
    end=base.index('*set, matids, ,', start)
    base=base[:start]+material_input(cfg)+base[end:]
    # Standalone deck has no dependency on an old Workbench directory.
    base='\n'.join(l for l in base.splitlines() if not any(x in l.lower() for x in
                    ('_wb_', '/wb,', 'file used for geometry attach:', 'c:\\ansys_sector_sim2')))
    base=re.sub(r'^/title,.*$', '/TITLE,Simulation 4 - coupled sector - exploratory',base,flags=re.M|re.I)
    base+=f'\nALLSEL,ALL\nTUNIF,{cfg["initial_temperature_C"]}\nFINISH\n'
    assert not re.search(r'^\s*SOLVE\b',base,re.M|re.I)
    (ROOT/'model_base.inp').write_text(base)
    (ROOT/'material_iteration4.apdl').write_text(material_input(cfg))
    (ROOT/'export_fields.mac').write_text(export_macro(mesh))
    w=cfg['windows_root']
    driver=f'''! Simulation 4. Executed ONLY by launch_iteration4.ps1 -Run.
/INPUT,model_base,inp
/SOLU
ANTYPE,TRANS,NEW
NROPT,FULL
THOPT,FULL
TRNOPT,FULL
TINTP,,,,1
AUTOTS,ON
NEQIT,60
KBC,1
ESTIF,1E-6
DMPOPTION,RNNN,NO
RESCONTROL,DEFINE,ALL,LAST,-1,,{cfg['output']['save_restart_generations']}
OUTRES,ALL,LAST
OUTRES,SVAR,LAST
FINISH
*DO,S4_LOOP,1,{cfg['numerics']['max_steps']}
  /DELETE,step_control,inp
  /SYS,{w}\\couple.cmd prepare
  S4_OK=0
  /INPUT,step_control,inp
  *IF,S4_OK,NE,1,THEN
    /COM,ITER4_PREPARE_FAILED_OR_MISSING
    /EXIT,NOSAVE
  *ENDIF
  *IF,S4_DONE,EQ,1,THEN
    *EXIT
  *ENDIF
  /SOLU
  *IF,S4_INDEX,GT,1,THEN
    ANTYPE,,REST,,,CONTINUE
  *ENDIF
  ! Restart restores old parameters. Read the external authoritative state again.
  /INPUT,step_control,inp
  /INPUT,apply_loads,inp
  TIME,S4_TARGET
  DELTIM,S4_DT,{cfg['minimum_dt_s']},S4_DT,OFF
  SOLVE
  /INPUT,export_fields,mac
  /DELETE,accepted,inp
  /SYS,{w}\\couple.cmd accept
  S4_OK=0
  /INPUT,accepted,inp
  *IF,S4_OK,NE,1,THEN
    /COM,ITER4_POSTPROCESS_OR_BALANCE_FAILED
    /EXIT,NOSAVE
  *ENDIF
*ENDDO
/COM,ITER4_CONTROLLER_STOPPED_CHECK_STATUS_JSON
/EXIT,NOSAVE
'''
    (ROOT/'run_iteration4.inp').write_text(driver)
    # A new process must restore its database before resuming. The last
    # accepted load-step index is explicit, never an unverified latest Rnnn.
    resume=driver[driver.index('*DO,S4_LOOP'):]
    resume=resume.replace('ANTYPE,,REST,,,CONTINUE','ANTYPE,,REST,S4_PREVIOUS,,CONTINUE')
    (ROOT/'resume_iteration4.inp').write_text('! Resume only a verified paused state.\n'+resume)
    python=r'C:\Program Files\ANSYS Inc\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe'
    (ROOT/'couple.cmd').write_text('@echo off\n"'+python+'" "'+w+'\\coupler.py" %1 --root "'+w+'"\nexit /b %ERRORLEVEL%\n')
    # Pure preprocessor/BC validation: no SOLVE, not even a coupon solve.
    from coupler import initial_state, prepare_step
    string_mesh=json.loads(json.dumps(mesh))
    s=initial_state(string_mesh,cfg)
    pre=['! NO SOLVE: validate all 64 exposed faces in a disposable database.',
         '/INPUT,model_base,inp','/GOPR','/SOLU','ANTYPE,TRANS,NEW',
         'NROPT,FULL','THOPT,FULL','ESTIF,1E-6',
         '/OUTPUT,validation/face_listing,txt']
    for layer in range(64):
        s['layer']=layer
        s['pending_kills']=[f['element'] for f in mesh['rows'][layer-1]] if layer else []
        _,loads=prepare_step(string_mesh,cfg,s)
        pre += ['/NOPR',loads,'ESEL,NONE']
        pre += [f'ESEL,A,ELEM,,{f["element"]}' for f in mesh['rows'][layer]]
        pre += ['ESEL,R,LIVE','/GOPR',f'/COM,ITER4_FACE_CASE_{layer:02d}_BEGIN',
                '*GET,S4_NE,ELEM,0,COUNT','*VWRITE,S4_NE',"('LIVE_HOT_ELEMENTS=',F8.0)",
                'SFELIST,ALL,CONV',f'/COM,ITER4_FACE_CASE_{layer:02d}_END']
    pre+=['/OUTPUT','/COM,ITER4_PREFLIGHT_COMPLETE_NO_SOLVE','FINISH','/EXIT,NOSAVE']
    assert not re.search(r'^\s*SOLVE\b','\n'.join(pre),re.M|re.I)
    (ROOT/'preflight_no_solve.inp').write_text('\n'.join(pre)+'\n')
    report=dict(nodes=len(nodes),solid_elements=len(elements),phe0_elements=sum(e['mat']==1 for e in elements.values()),
                radial_rows=64,faces_per_row=[len(r) for r in mesh['rows']],outer_faces=len(mesh['outer']),
                hot_surface_nodes=303,first_area_m2=sum(f['area'] for f in mesh['rows'][0]),
                phe0_volume_m3=sum(e['volume'] for e in elements.values() if e['mat']==1),
                source_sha256=hashlib.sha256((ROOT/'source/simulation3_executed_ds.dat').read_bytes()).hexdigest(),
                model_sha256=hashlib.sha256(base.encode()).hexdigest(),solve_started=False)
    (ROOT/'validation/mesh_preparation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
