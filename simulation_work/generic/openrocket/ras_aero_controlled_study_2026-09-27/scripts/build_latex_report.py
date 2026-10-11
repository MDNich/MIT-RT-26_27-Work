"""Generate a standalone LaTeX report using the solid-propulsion report style.

All plot coordinates and the existing team-logo outlines are embedded so the
built-in LaTeX editor does not need additional project assets.
"""
from pathlib import Path
import csv,html,json,re,xml.etree.ElementTree as ET
import numpy as np
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'comparison-results.json').read_text())

def esc(t):
    m={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}','<':r'\textless{}','>':r'\textgreater{}'}
    return ''.join(m.get(c,c) for c in html.unescape(t))

def inline(t):
    t=t.replace('<br/>',' ')
    t=re.sub(r'<link href="([^"]+)"[^>]*>(.*?)</link>',lambda m:'@@LINK@@'+m.group(1)+'@@LABEL@@'+m.group(2)+'@@END@@',t)
    parts=re.split(r'(\*\*.*?\*\*|@@LINK@@.*?@@END@@)',t)
    out=[]
    for p in parts:
        if p.startswith('**'):out.append(r'\textbf{'+esc(p[2:-2])+'}')
        elif p.startswith('@@LINK@@'):
            url,label=p[8:-7].split('@@LABEL@@');out.append(r'\href{'+url.replace('%',r'\%')+'}{'+esc(label)+'}')
        else:out.append(esc(p))
    return ''.join(out).replace('m/s2',r'm/s$^2$')

def logo():
    svg=ET.parse(R/'assets/rtlogo.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    defs={g.attrib['id']:g.find('s:path',ns).attrib['d'] for g in svg.findall('.//s:defs/s:g/s:g',ns)}
    paths=[]
    for el in svg:
        tag=el.tag.split('}')[-1]
        if tag=='defs':continue
        col='teamred' if '68.62793%' in el.attrib.get('fill','') else 'black'
        if tag=='g':
            u=el.find('s:use',ns)
            if u is None:continue
            d=defs[u.attrib['{http://www.w3.org/1999/xlink}href'][1:]];ox=float(u.attrib.get('x',0));oy=float(u.attrib.get('y',0))
        else:d=el.attrib['d'];ox=oy=0
        tokens=re.findall(r'[MLCZ]|[-+]?(?:\d*\.\d+|\d+)',d);i=0;st=[]
        def point():
            nonlocal i
            x=float(tokens[i])+ox;y=float(tokens[i+1])+oy;i+=2
            return f'({x:.6f},{y:.6f})'
        while i<len(tokens):
            cmd=tokens[i];i+=1
            if cmd=='M':st.append(point())
            elif cmd=='L':st.append('-- '+point())
            elif cmd=='C':a,b,c=point(),point(),point();st.append('.. controls '+a+' and '+b+' .. '+c)
            elif cmd=='Z':st.append('-- cycle')
            else:raise ValueError(cmd)
        paths.append(r'\path[fill='+col+',draw=none,even odd rule] '+' '.join(st)+';')
    return '\n'.join([r'\newcommand{\teamlogo}{%',r'\resizebox{4.8cm}{!}{\begin{tikzpicture}[x=1pt,y=-1pt]',r'\path[use as bounding box] (0,0) rectangle (1620,758);']+paths+[r'\end{tikzpicture}}}'])

def read(p):
    rows=list(csv.DictReader(p.open()));return {k:np.array([float(r[k]) for r in rows]) for k in rows[0] if k!='Stage'}
def coords(x,y):
    ix=np.unique(np.r_[np.linspace(0,len(x)-1,min(130,len(x)),dtype=int),np.argmax(y),np.argmin(y)])
    return ' '.join(f'({x[i]:.7g},{y[i]:.7g})' for i in ix)

def apogeeplot():
    out=[r'\begin{figure}[H]\centering',r'\begin{tikzpicture}',r'''\begin{axis}[width=.875\textwidth,height=6.0cm,xbar,bar width=5pt,
xmin=-35,xmax=0,ymin=-.6,ymax=4.6,ytick={0,1,2,3,4},
yticklabels={4 in / square,4 in / rough square*,4 in / bevel,2.26 in / square,2.26 in / bevel},
y dir=reverse,xlabel={Apogee difference $100(h_{\mathrm{RAS}}/h_{\mathrm{OR}}-1)$ [\%]},
legend style={at={(.03,.03)},anchor=south west,draw=none,fill=white},legend columns=2,
axis on top=false,xmajorgrids=true,ymajorgrids=false,grid style={gray!25},font=\small]''']
    for motor,col in [('I500T-14A','B'),('J570W','burntorange')]:
        v=[x['delta_pct']['apogee_m'] for x in D if x['motor']==motor]
        out.append(r'\addplot[fill='+col+',draw='+col+'] coordinates {'+' '.join(f'({val:.7f},{j})' for j,val in enumerate(v))+'};')
        out.append(r'\addlegendentry{'+motor.replace('-14A','')+'}')
    out += [r'\end{axis}\end{tikzpicture}',r'\caption{Apogee differences after matching geometry and fully turbulent flow. B02 (asterisk) retains a numerical roughness mismatch and is excluded from clean solver attribution.}\label{fig:apogee}',r'\end{figure}']
    return '\n'.join(out)

def dragplot():
    out=[r'\begin{figure}[H]\centering',r'\begin{tikzpicture}',r'''\begin{groupplot}[group style={group size=2 by 2,horizontal sep=1.3cm,vertical sep=1.85cm},
width=.455\textwidth,height=5.0cm,xlabel={Mach},ylabel={$C_D$},ymin=0,
grid=major,grid style={gray!25},tick label style={font=\small},label style={font=\small},title style={font=\small},
legend style={font=\scriptsize,draw=none,fill=white,at={(.02,.03)},anchor=south west}]''']
    for k,(base,title) in enumerate([('B01-smooth-square','4 in / square'),('B03-smooth-bevel','4 in / bevel'),('B04-slender-square','2.26 in / square'),('B05-slender-bevel','2.26 in / bevel')]):
        a=read(R/'evidence'/(base+'-turbulent-J570W-same-state.csv'));sel=(a['ras_thrust_N']==0)&(a['velocity_m_s']>30)
        out.append(r'\nextgroupplot[title={'+title+'}]')
        for key,col,lab in [('or_cd','B','MIT OR'),('ras_cd','burntorange','RASAero')]:
            out.append(r'\addplot['+col+r',thick,mark=*,mark size=.65pt,mark repeat=10] coordinates {'+coords(a['ras_mach'][sel],a[key][sel])+'};')
            if k==0:out.append(r'\addlegendentry{'+lab+'}')
    out += [r'\end{groupplot}\end{tikzpicture}',r'\caption{J570W coast-branch drag at common reported Mach and altitude, above \SI{30}{m.s^{-1}}. MIT OR retains its ISA atmosphere. Curves are subsampled for display only; statistics use the full histories.}\label{fig:drag}',r'\end{figure}']
    return '\n'.join(out)

PREAMBLE=r'''% Standalone report; no external figures or bibliography files required.
% Style: simulation_work/solidprop/newmotor_phenolic_study/v0/docs/en/
%        newmotor_phenolic_v0_report.tex and phenolic_case_study/docs/en/
%        phenolic_pyrolysis_ablation_report.tex.
\documentclass[oneside,openany]{amsdtx}
\usepackage[margin=.75in]{geometry}
\usepackage{graphicx,float,amsmath,amssymb,url,multicol,booktabs,bm,array,enumitem}
\usepackage[dvipsnames]{xcolor}
\usepackage[allcolors=black]{hyperref}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage{lmodern,siunitx,tabularx,longtable,caption}
\captionsetup{font=small,labelfont=bf,labelsep=period}
\captionsetup[longtable]{width=.96\textwidth}
\usepackage{tikz,pgfplots}
\usepgfplotslibrary{groupplots}
\pgfplotsset{compat=1.18}
\definecolor{b}{HTML}{3C78D8}\definecolor{B}{HTML}{08357E}\definecolor{g}{HTML}{38761D}
\definecolor{r}{HTML}{7A0101}\definecolor{burntorange}{HTML}{A04A00}
\definecolor{teamred}{RGB}{175,31,57}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\protected\def\code#1{\texttt{\detokenize{#1}}}
\sisetup{locale=US,per-mode=symbol,range-phrase=--,range-units=single}
\setcounter{secnumdepth}{3}\setcounter{tocdepth}{2}
\setlength{\emergencystretch}{2em}
\hfuzz=0.5pt
\title{~\\[-2em]\sc Controlled Flight and Aerodynamic Study:\\
MIT OpenRocket and RASAero II}
\author{\sc MIT Rocket Team --- Flight Simulation Studies}
\date{\sc September 27, 2026}
\hypersetup{pdftitle={Controlled Flight and Aerodynamic Study: MIT OpenRocket and RASAero II},pdfauthor={MIT Rocket Team}}
'''
FRONT=r'''
\begin{document}
\selectlanguage{english}
\maketitle
\begin{center}
\begin{minipage}{.43\textwidth}\centering\teamlogo\end{minipage}\hfill
\begin{minipage}{.47\textwidth}\centering
{\large\sc MIT OpenRocket}\\[.7em]
{\large\sc RASAero II}\\[.9em]
Five flight designs --- two motors\\
92 aerodynamic configurations\\
Windows 11 virtual machine
\end{minipage}
\end{center}
\vspace{.4em}
{\small\setcounter{tocdepth}{1}\tableofcontents}\setcounter{tocdepth}{2}
\vfill
\begin{center}\begin{minipage}{.96\textwidth}\small
\textbf{Purpose of this document.} This report compares ten paired flight predictions
for five newly constructed OpenRocket models. It separates export and model-description
differences from aerodynamic and numerical differences, records the controlled Windows
execution, and identifies evidence-based improvements to MIT OpenRocket. Eight cases
have matched geometry and roughness; the two rough-finish cases are retained as an
explicitly confounded export diagnostic. A follow-on investigation isolates aerodynamic mechanisms with an initial 25-case investigation and a 92-configuration coefficient atlas, without modifying MIT OR. Agreement between programs is not physical
validation against measured flight data.
\end{minipage}\end{center}
\vfill
\clearpage
\section{Principal findings}
'''
TABLES=[
('Nominal geometry and dry mass properties.','tab:geometry',[.32,.31,.31]),
('Design matrix and fin-edge treatment.','tab:designs',[.23,.34,.37]),
('Model-equivalence audit and remaining implementation differences.','tab:audit',[.16,.44,.34]),
('Primary ascent performance. Percent differences use MIT OR as denominator.','tab:flight',[.07,.10,.22,.12,.22,.21]),
('Time to apogee and maximum ascent acceleration.','tab:time',[.10,.12,.34,.38]),
('Drag coefficient at the RASAero maximum-speed row, J570W cases.','tab:cd',[.28,.22,.22,.22]),
('Drag-substitution diagnostic. Both differences use RASAero as denominator.','tab:replay',[.12,.13,.23,.25,.21]),
('Numerical and input-consistency checks.','tab:checks',[.26,.68]),
('Sensitivity to the RASAero flow assumption.','tab:flow',[.12,.12,.27,.27,.16]),
('Prioritized MIT OpenRocket improvements and acceptance evidence.','tab:recommendations',[.18,.44,.32]),
('Retained study files and their roles.','tab:files',[.27,.67]),
]

def table(rows,i):
    caption,label,widths=TABLES[i]
    header=rows[0];data=rows[2:]
    assert len(header)==len(widths),(i,header)
    # Explicit widths leave room for inter-column padding inside the text block.
    n=len(widths);cols='@{}'+''.join('L{'+f'{w:.3f}'+r'\textwidth}' for w in widths)+'@{}'
    result=[r'{\small\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.16}',r'\begin{longtable}{'+cols+'}',r'\caption{'+caption+r'}\label{'+label+r'}\\',r'\toprule', ' & '.join(r'\textbf{'+inline(x)+'}' for x in header)+r'\\',r'\midrule\endfirsthead',r'\multicolumn{'+str(n)+r'}{l}{\small\itshape Table \thetable\ continued}\\',r'\toprule',' & '.join(r'\textbf{'+inline(x)+'}' for x in header)+r'\\',r'\midrule\endhead',r'\bottomrule\endfoot']
    result.extend(' & '.join(inline(x) for x in row)+r'\\' for row in data)
    result.extend([r'\end{longtable}}'])
    return '\n'.join(result)

raw=(R/'report.md').read_text()
raw=raw.replace('Machine-readable flight statistics and diagnostics; report.md is the editable report companion.','Machine-readable flight statistics and diagnostics; mit-or-rasaero-study.tex is the standalone report source.')
raw=raw.replace('after matching geometry and fully turbulent flow','after matching geometry and fully turbulent flow')
lines=raw.splitlines();fixed=[];i=0
while i<len(lines):
    line=lines[i]
    if line.startswith('|'):
        while not line.rstrip().endswith('|'):
            i+=1;line+=' '+lines[i]
    fixed.append(line);i+=1
blocks='\n'.join(fixed).split('\n\n');out=[PREAMBLE,logo(),FRONT];nt=0
for block in blocks:
    block=block.strip()
    if not block or block.startswith('# MIT ') or block.startswith('27 September 2026 |'):continue
    if block.startswith('## '):
        name=re.sub(r'^## \d+\.\s*','',block);out.append(r'\clearpage\section{'+esc(name)+'}');continue
    if block.startswith('### '):out.append(r'\subsection{'+esc(block[4:])+'}');continue
    if block.startswith('|'):
        rows=[[x.strip() for x in line.split('|')[1:-1]] for line in block.splitlines()]
        out.append(table(rows,nt));nt+=1;continue
    if block.startswith('!['):out.append(apogeeplot() if 'apogee-difference' in block else dragplot());continue
    if block.startswith('MIT JAR SHA-256:'):
        out += [r'\noindent MIT JAR SHA-256:\\{\footnotesize\url{d39a932bd26ba8ac9235c01332a93492f90e01f2a465e488d7fa541f31e3f4e6}}\\',r'Source HEAD: {\footnotesize\url{e8867552ba16bf53dc67ea4da55fc3c45697048b}} (plus local custom changes).'];continue
    out.append(inline(block)+'\n')
    if block.startswith('Three export issues'):
        out.append(r'\textbf{Aerodynamic follow-up.} Section~\ref{sec:aero} separates body and net fin contributions. It identifies a near-zero tangent-ogive nose-pressure term, loss of bevel sensitivity in the detached-shock fallback, and a body-length dependence in fin friction. An independent nose-term trial reduces mean absolute body-drag error by 84\% over six configurations at Mach 1.32--3. No MIT OR application/source changes were made.')
    if block.startswith('RASAero was configured, run'):
        out.append(r'\textbf{Completed extension.} Section~\ref{sec:extended} expands the data to 92 configurations and 82,800 common Mach/angle points, with 42 plot sheets. It tests nose shapes, fin geometry, physical roughness, transition, nozzle area, scale, normal force and CP without modifying the installed OR engine.')
    if block.startswith('Primary results:'):
        out.append(r'\begin{equation}\delta_h=100\left(\frac{h_{\mathrm{RAS}}}{h_{\mathrm{OR}}}-1\right)\,\%.\label{eq:apogee-difference}\end{equation}')
assert nt==len(TABLES),nt
from aero_report import build_aero_section
out.append(build_aero_section(R))
from extended_atlas_report import build_extended
out.append(build_extended(R))
out.append(r'\end{document}')
target=R/'mit-or-rasaero-study.tex';target.write_text('\n\n'.join(out)+'\n')
print(target, target.stat().st_size)
