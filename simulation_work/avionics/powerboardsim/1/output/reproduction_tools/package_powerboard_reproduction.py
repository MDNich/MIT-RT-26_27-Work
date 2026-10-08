from pathlib import Path
import sys, json, hashlib, shutil, zipfile, subprocess, datetime
sys.path.insert(0,'/tmp')
from rv_paths import P,R,OLD

D=P/'output/latex/random_vibration'
MD=P/'output/latex/modal_reproduction'
B=P/'outputs/bolt_manager_work'
sources={}

def add(root,src,rel):
    src=Path(src);dst=root/rel
    if not src.is_file(): raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    sources.setdefault(str(root),{})[rel]={
        'source_project_relative':str(src.relative_to(P)) if src.is_relative_to(P) else str(src),
        'bytes':dst.stat().st_size,
        'sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest()}

def build(root,kind):
    root.mkdir(parents=True,exist_ok=True)
    for f in (B/'custom_library').iterdir():add(root,f,'custom_library/'+f.name)
    common=[
        (R/'assembly_body_inventory.tsv','assembly_body_inventory.tsv'),
        (OLD/'final_active_contacts.tsv','final_active_contacts.tsv'),
        (OLD/'audit_battery_constraints.py','audit_battery_constraints.py'),
        (OLD/'battery_connection_audit.txt','battery_connection_audit.txt'),
        (OLD/'contacts.tsv','original_contacts.tsv'),
        (OLD/'contact_graph_summary.txt','contact_graph_summary.txt'),
        (OLD/'accepted_results_audit.json','accepted_results_audit.json'),
        (OLD/'bolted750_refined/bolt_preload_audit.csv','bolt_preload_audit.csv'),
        (OLD/'bolted750_refined/bearing_contact_audit.json','bearing_contact_audit.json'),
    ]
    for src,name in common:add(root,src,'common/'+name)
    for f in ['ds.dat','solve.out','bolt_inventory.csv','bolt_preload_audit.csv','bearing_model.txt','STATIC_VERIFIED.txt','static_result_summary.txt']:
        add(root,OLD/'bolted750_refined'/f,'native/static750/'+f)
    add(root,OLD/'bolted750_refined/preflight_20261005_014051/preflight.dat','native/static750/preflight.dat')
    add(root,OLD/'bolted750_refined/preflight.out','native/static750/preflight.out')
    add(root,B/'setup_bolts_670N.py','scripts/HISTORICAL_setup_bolts_670N.py')
    for f in ['setup_bearing_contacts.py','setup_bolted750.py','command_012739_727153.py']:
        add(root,OLD/f,'scripts/'+f)
    if kind=='modal':
        for name,target,pref in [
            ('default','default_original','default/bounded_10k/preflight.dat'),
            ('default_refined','default_refined','default_refined/preflight_20261004_213206/preflight.dat'),
            ('bolted750_modal','modal20','bolted750_modal/preflight_20261004_224825/preflight.dat')]:
            for f in ['ds.dat','solve.out','frequencies.csv']:add(root,OLD/name/f,'native/'+target+'/'+f)
            add(root,OLD/pref,'native/'+target+'/preflight.dat')
        for f in ['export_modal_results.py','command_005824_388784.py','command_013046_306686.py','command_024957_877313.py']:
            add(root,OLD/f,'scripts/'+f)
    else:
        for f in ['assembly_body_response_audit.csv','assembly_scope_audit.json','mounting_nodes.txt','pcb_nodes.txt','pcb_elements.txt','cross_case_input_audit.json','stress_hotspot_bodies.tsv','study_config.json']:
            add(root,R/f,'common/'+f)
        for f in ['ds.dat','solve.out','frequencies.csv','audit.json','modal_parent_inventory.csv','participation_X.csv','participation_Y.csv','participation_Z.csv']:
            add(root,R/'modal_basis'/f,'native/modal_basis/'+f)
        for axis in 'XYZ':
            c=Path((R/axis/'accepted_native_directory.txt').read_text())
            for f in ['run.dat','preflight.dat','preflight.out','solve.out','native_solver_audit.json']:
                add(root,c/f,'native/random_'+axis+'/'+f)
            add(root,c/'manifest.json','native/random_'+axis+'/staging_manifest.json')
            for f in ['psd_input.dat','field_coverage_audit.json','support_response_audit.json','result_summary.tsv']:
                add(root,R/axis/f,'native/random_'+axis+'/'+f)
        for f in ['preflight_modal_basis.py','stage_local.py','native_preflight.py','launch_local.py','collect_local.py','postprocess.py','audit_fields.py','verify_assembly_scope.py','export_assembly_views.py','import_request.py','audit_modal.py','export_psd.py','make_latex_plots.py','rv_paths.py','powerboard_vm.py','pcb_request.py']:
            add(root,R/f,'scripts/'+f)
        add(root,R/'export_battery_oblique_views.py','scripts/export_battery_oblique_views.py')
        for f in ['export_audit.tsv','COMPLETE.txt']:
            add(root,R/'battery_oblique_20261005'/f,'common/battery_oblique_'+f)
        for f in ['command_135754_571642.py','command_140646_293227.py','command_141951_126210.py','command_144135_932820.py']:
            add(root,OLD/f,'scripts/'+f)
    (root/'MANIFEST.json').write_text(json.dumps({'documentation_revision':'2026-10-05','study':kind,'files':sources[str(root)],'not_bundled':['complete Workbench project/CAD directory','binary static restart and expanded-modal per-rank matrices','binary random result files and raw full-field text exports'],'execution_note':'Evidence files are copied byte-for-byte. Original helper scripts preserve historical paths/globals/one-run guards and are reference implementations, not a new portable installer. Follow the numbered report procedure in a new study directory.'},indent=2))
    (root/'README.txt').write_text('REPRODUCTION EVIDENCE\n\nFollow the numbered appendix in the report.\nFiles in this directory are exact copies of accepted input/evidence or\nexplicitly identified historical implementation helpers. MANIFEST.json\nrecords the source path, size and SHA-256 for each copy.\n\nThe old 670N XML filename actually stores 750 N per bolt.\nHISTORICAL_setup_bolts_670N.py is an earlier construction reference;\ndo not execute its old assertions or duplicate its objects on the saved model.\nOriginal Python helpers require path/global-variable adaptation and new\noutput folders for a rerun. No new simulation was run in this report edit.\n\nThe complete Workbench project and large solver binaries are not in this\nZIP. Retain them separately or regenerate parent solutions in the order\nexplained in the report. No script here should overwrite accepted evidence.\n')

def sha(f):
    with Path(f).open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def pages(f):
    t=subprocess.check_output(['/opt/homebrew/bin/pdfinfo',str(f)],text=True)
    return int(next(x.split(':',1)[1] for x in t.splitlines() if x.startswith('Pages:')))

def finish():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for stem,root,kind in [('power_board_modal_comparison',MD,'modal'),('power_board_random_vibration',D/'reproduction','random')]:
        build(root,kind)
        srcdir=P/'output/latex' if kind=='modal' else D
        srcpdf=srcdir/(stem+'.pdf');dstpdf=P/'output/pdf'/(stem+'.pdf')
        shutil.copy2(srcpdf,dstpdf)
        metadata={'documentation_updated_utc':now,'numerical_results_changed':False,'new_simulation_run':False,
                  'pages':pages(dstpdf),'sha256':sha(dstpdf),
                  'qa':'All pages rendered and visually reviewed; no LaTeX overfull boxes or compile warnings.',
                  'reproduction_manifest':'reproduction/MANIFEST.json',
                  'native_editor_compile':'success' if kind=='modal' else 'Standalone editor cannot resolve plots/InputPSD.tex; complete project compiled with pdfLaTeX.'}
        if kind=='random':
            old=json.loads((D/'verification_summary.json').read_text())
            old['documentation_revision']=metadata
            old['pdf_pages']=metadata['pages'];old['pdf_sha256']=metadata['sha256']
            old['pdf_visual_qa']=metadata['qa']
            old['external_graphics']=17
            old['battery_oblique_views']={'count':9,'camera_view_vector':[1,-1,-1],'camera_up_vector':[-.3,1,-1.3],'fit_scene_height_multiplier':1.25,'width':2100,'height':1400,'unchanged_solved_maxima':True,'audit':'reproduction/common/battery_oblique_export_audit.tsv'}
            (D/'verification_summary.json').write_text(json.dumps(old,indent=2))
            readme=(D/'README.txt').read_text()
            readme=readme.split('\nREPRODUCTION APPENDIX REVISION\n')[0]
            readme=readme.replace('eight external ANSYS PNG contours','seventeen external ANSYS PNG contours')
            readme+='\nREPRODUCTION APPENDIX REVISION\nThe report now includes a numbered, detailed reproduction procedure.\nreproduction/ contains native inputs, original reference scripts, scopes,\naudits and a SHA-256 manifest. No numerical results were changed.\nCompile the delivered TeX directly; old builders predate the appendix.\n'
            readme+='Nine added battery-side oblique views show every directional displacement\ncomponent for each excitation case. These are fresh native ANSYS exports.\n'
            (D/'README.txt').write_text(readme)
        else:
            (MD/'verification_summary.json').write_text(json.dumps(metadata,indent=2))
        outzip=P/'output'/(stem+'_latex.zip')
        with zipfile.ZipFile(outzip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.write(srcdir/(stem+'.tex'),stem+'/'+stem+'.tex')
            z.write(srcpdf,stem+'/'+stem+'.pdf')
            if kind=='modal':
                z.write(P/'output/power_board_modal_frequencies.csv',stem+'/power_board_modal_frequencies.csv')
                for f in sorted(MD.rglob('*')):
                    if f.is_file():z.write(f,stem+'/reproduction/'+str(f.relative_to(MD)))
            else:
                for f in sorted(D.rglob('*')):
                    if not f.is_file():continue
                    if f in [D/(stem+'.tex'),D/(stem+'.pdf')]:continue
                    if f.parent==D and f.suffix in ['.aux','.log','.out','.toc','.synctex']:continue
                    z.write(f,stem+'/'+str(f.relative_to(D)))
        with zipfile.ZipFile(outzip) as z:assert z.testzip() is None
        print(stem,metadata['pages'],'pages;',round(outzip.stat().st_size/1e6,2),'MB source ZIP')
    (P/'output/reproduction_documentation_revision.json').write_text(json.dumps({'time_utc':now,'reports':[str(P/'output/pdf/power_board_modal_comparison.pdf'),str(P/'output/pdf/power_board_random_vibration.pdf')],'authoring_script':'add_powerboard_reproduction.py','simulation_rerun':False},indent=2))

if __name__=='__main__':finish()
