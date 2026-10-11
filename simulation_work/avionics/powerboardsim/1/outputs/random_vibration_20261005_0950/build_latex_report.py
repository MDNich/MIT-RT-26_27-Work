from pathlib import Path
import csv,json,re,shutil,sys
sys.path.insert(0,'/tmp')
from rv_paths import *
config=json.loads((R/'study_config.json').read_text())
# The report uses ordinary external graphic files beside its LaTeX source.
def tex(s):
 d={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
 return ''.join(d.get(ch,ch) for ch in str(s))
def para(s):return tex(s)+'\n\n'
def table(headers,rows,spec):
 return '\\begin{center}\n\\begin{tabular}{'+spec+'}\n\\toprule\n'+' & '.join('\\textbf{'+tex(v)+'}' for v in headers)+r' \\'+'\n\\midrule\n'+''.join(' & '.join(tex(v) for v in row)+r' \\'+'\n' for row in rows)+'\\bottomrule\n\\end{tabular}\n\\end{center}\n'
def fig(name,caption,width='.76\\linewidth'):
 return '\\begin{center}\n\\includegraphics[width='+width+']{figures/'+name+'}\n\\captionof{figure}{'+tex(caption)+'}\n\\end{center}\n'
def plotfig(name,caption,width=r'.86\linewidth'):
 return r'\begin{center}\begin{minipage}{'+width+r'}\input{plots/'+name+r'.tex}\end{minipage}\captionof{figure}{'+tex(caption)+r'}\end{center}'+'\n'
def heading(s):return '\\ReportHeading{'+tex(s)+'}\n'
def page(s):return '\\clearpage\\PageTitle{'+tex(s)+'}\n'
content=json.loads((R/'report_content.json').read_text())
old=(P/'output/latex/power_board_modal_comparison.tex').read_text()
pre=old[:old.index('% Low-level image wrapper')]
pre=re.sub(r'% Self-contained.*?% The editable.*?\n','% Figures are ordinary external graphics in the figures/ directory.\n',pre,flags=re.S)
pre=pre.replace('Power-board modal comparison','Power-board random vibration').replace('Power board: natural-frequency comparison','Power board: random vibration').replace('Modal study','Random vibration')
pre=re.sub(r'% Results are from.*\n','% Random-vibration results from 5 October 2026.\n',pre)
pre+=r'\usepackage{pgfplots}\pgfplotsset{compat=1.18}'+'\n'
body=r'''\newcommand{\ReportBody}{%
\PageTitle{Power board: random vibration}
{\large\color{Teal}Separate X, Y and Z base excitation \enspace | \enspace 2\% assumed damping}\par
{\small Six locked bolts at 750 N each. ANSYS Mechanical/MAPDL 2026 R1.02.}\par
'''
for x in content['summary']:body+=para(x)
body+=heading('PCB random-response RMS')
body+=table(['Base axis','Max component u (mm)','Component','PCB stress (MPa)'],content['headline_rows'],'c r c r')
body+=para('Displacements are relative to the mounting supports. Stress is the unaveraged Segalman--Fulcher equivalent-stress RMS, excluding the static mean stress. These exploratory elastic values are not a pass/fail strength assessment.')
body+=r'\textbf{Interpretation:} '+para(content['stress_alert'])
body+=heading('Specified acceleration spectrum')
body+=r'\begin{center}\begin{minipage}[c]{.32\linewidth}'+'\n'
body+=table(['Hz','PSD (g²/Hz)'],[(int(f),str(v)) for f,v in zip(config['frequency_hz'],config['acceleration_psd_g2_per_hz'])],'r r').replace('g²','g$^2$')
body+=r'\end{minipage}\hfill\begin{minipage}[c]{.65\linewidth}\input{plots/InputPSD.tex}\end{minipage}'+'\n'
body+=r'\captionof{figure}{Specified PSD with power-law interpolation between the supplied points. Integrated input: 14.136 g RMS.}\end{center}'+'\n'
body+=para('The Mechanical load panel may display 15.310 g RMS because its display uses a linear trapezoidal integral of the four points. The piecewise log-log spectrum integrates to 14.136 g RMS; no input points were changed.')
body+=page('Directional response results')
for title,key in [('PCB directional displacement RMS (mm)','pcb_u_rows'),('PCB absolute acceleration RMS (g)','pcb_a_rows'),('Whole-assembly directional displacement RMS (mm)','all_u_rows'),('Whole-assembly absolute acceleration RMS (g)','all_a_rows')]:
 body+=heading(title);body+=table(['Base axis','X response','Y response','Z response'],content[key],'c r r r')
body+=heading('Stress and PCB strain')
body+=table(['Base axis','PCB stress (MPa)','Assembly stress (MPa)'],content['stress_rows'],'c r r')
body+=table(['Base axis','PCB strain X (µε)','Y (µε)','Z (µε)'],content['strain_rows'],'c r r r').replace('µε',r'$\mu\varepsilon$')
body+=para('Each table entry is a spatial maximum for that component; maxima need not occur at the same node. No vector sum of directional RMS maxima is reported. Three times a directional RMS value is a conventional 3-sigma estimate under a Gaussian assumption, not a guaranteed mission maximum. Equivalent stress is not Gaussian.')
body+=page('Whole-assembly response: X and Y excitation')
body+=para('The solved model contains 208 meshed, unsuppressed bodies, including 172 imported electronic-component bodies. Every body has finite response values in all three cases. The PCB-only figures later in this report are scoped views of this same assembled solution.')
for axis in ['X','Y']:
 row=next(r for r in csv.DictReader((R/'assembly_image_results.tsv').open(),delimiter='\t') if r['axis']==axis)
 comp=row['name'].split()[2];maximum=float(row['maximum'].split()[0])*1000
 body+=fig('Assembly'+axis,f'{axis}-axis base excitation, whole assembly: {comp}-direction RMS displacement. Spatial maximum {maximum:.5g} mm. PCB, component bodies, batteries and hardware are included. Legend units are metres.','.72\\linewidth')
body+=page('Whole-assembly response: Z excitation and battery side')
body+=fig('AssemblyZ','Z-axis base excitation, whole assembly: Z-direction RMS displacement, maximum 0.080600 mm. The populated component side and fastening hardware are visible.','.72\\linewidth')
body+=fig('AssemblyBack','Battery-side view of the same Z-excitation result. The three cell bodies and the six battery fasteners are visible. All figures show the full assembly result; hidden surfaces are occluded by the viewing direction.','.72\\linewidth')
body+=para('These are directional RMS response contours, not instantaneous vibration shapes. Each contour uses its own range. Imported ECAD components are represented by their meshed solids; this does not establish detailed package or solder-joint accuracy.')
body+=page('PCB deformation under X and Y excitation')
for axis in ['X','Y']:body+=fig('Disp'+axis,content['image_captions'][axis])
body+=para('Contours show the largest PCB displacement component for each excitation case. Any displayed geometric deformation is a visualization scale; an RMS field is not an instantaneous deformed configuration.')
body+=page('PCB deformation and stress under random vibration')
body+=fig('DispZ',content['image_captions']['Z'])
body+=fig('WorstStress',content['stress_caption'])
body+=page('Model and numerical checks')
for title,paragraphs in content['method_sections']:
 body+=heading(title)
 for x in paragraphs:body+=para(x)
body+=table(['Case','Errors','Warnings','Finite fields','Support nodes'],content['solver_rows'],'c r r r r')
body+=para('The three input decks were compared and differ only in excitation axis, analysis title and runtime location. Inherited warnings remain part of the qualification limits below.')
body+=page('Prestressed modal basis')
freq=list(csv.DictReader((R/'modal_basis/frequencies.csv').open()))
rows=[]
for i in range((len(freq)+1)//2):
 l=freq[i];j=i+(len(freq)+1)//2;r=freq[j] if j<len(freq) else None
 rows.append([l['rank'],f"{float(l['frequency_hz']):.3f}",r['rank'] if r else '',f"{float(r['frequency_hz']):.3f}" if r else ''])
body+=table(['Mode','Frequency (Hz)','Mode','Frequency (Hz)'],rows,'r r r r')
body+=plotfig('ModalEffectiveMass','Cumulative modal effective mass as a fraction of total directional mass. The shaded band is the 20--2000 Hz input range. A frequency cutoff alone does not establish response convergence.','.86\\linewidth')
body+=page('Qualification and traceability')
for title,paragraphs in content['qualification_sections']:
 body+=heading(title)
 for x in paragraphs:body+=para(x)
body+=heading('References')+'\\begin{enumerate}\n'
for title,url in content['references']:body+='\\item \\href{'+url+'}{'+tex(title)+'}.\n'
body+='\\end{enumerate}\n}\n'
assets=[('Assembly'+axis,R/axis/'assembly_displacement.png') for axis in ['X','Y','Z']]+[('AssemblyBack',R/'Z/assembly_back.png')]+[('Disp'+axis,R/axis/'pcb_displacement.png') for axis in ['X','Y','Z']]+[('WorstStress',R/content['worst_stress_axis']/'pcb_equivalent_stress.png')]
outdir=P/'output/latex/random_vibration'
figdir=outdir/'figures';figdir.mkdir(parents=True,exist_ok=True)
for stale in ['InputPSD.pdf','ModalEffectiveMass.pdf']:
 p=figdir/stale
 if p.exists():p.unlink()
for name,path in assets:shutil.copy2(path,figdir/(name+path.suffix))
out=outdir/'power_board_random_vibration.tex'
out.write_text(pre+body+'\n\\begin{document}\n\\ReportBody\n\\end{document}\n')
print(out)
