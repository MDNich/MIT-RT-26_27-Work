"""Standalone PGFPlots coefficient atlas, built from retained real solver outputs."""
import json,math,csv
import numpy as np

def esc(t):
 m={'&':r'\&','%':r'\%','_':r'\_','#':r'\#'}
 return ''.join(m.get(c,c) for c in str(t))
def coord(c):
 x=np.array(c['x']);y=np.array(c['y']);assert np.all(np.isfinite(x)) and np.all(np.isfinite(y))
 if len(x)>160:
  tolerance=max(1e-6,float(np.ptp(y))*1e-3)
  ix={0,len(x)-1,int(np.argmax(y)),int(np.argmin(y))};ix.update(range(0,len(x),5))
  def refine(a,b):
   if b-a<2:return
   estimate=y[a]+(y[b]-y[a])*(x[a+1:b]-x[a])/(x[b]-x[a]);errors=np.abs(y[a+1:b]-estimate);j=int(np.argmax(errors))+a+1
   if errors[j-a-1]>tolerance:ix.add(j);refine(a,j);refine(j,b)
  anchors=sorted(ix)
  for a,b in zip(anchors[:-1],anchors[1:]):refine(a,b)
  ix=np.array(sorted(ix));approx=np.interp(x,x[ix],y[ix]);assert np.max(abs(approx-y))<=tolerance*1.000001
  x=x[ix];y=y[ix]
 return ' '.join(f'({a:.6g},{b:.7g})' for a,b in zip(x,y))
def col(s):return {'#08357E':'B','#A04A00':'burntorange','#38761D':'g','#777777':'atlasgray'}[s]
def style(c):return col(c['color'])+(',dashed' if c['style']=='--' else '')
def figure(f):
 ps=f['panels'];rows=math.ceil(len(ps)/2);leg={}
 for p in ps:
  for c in p['curves']:leg.setdefault(c['label'],c)
 ncols=2 if any(len(x)>26 for x in leg) else min(3,len(leg));entries=[]
 for lab,c in leg.items():entries.append(r'\tikz[baseline=-.5ex]{\draw[thick,'+style(c)+r'] (0,0)--(.40,0);}\ '+esc(lab))
 legend=[]
 for i in range(0,len(entries),ncols):legend.append(' & '.join(entries[i:i+ncols])+r'\\')
 h='4.45cm' if rows==3 else '5.65cm'
 out=[r'\clearpage\subsubsection*{'+esc(f['title'])+'}',r'\begin{figure}[H]\centering',r'{\footnotesize\begin{tabular}{'+('l'*ncols)+'}',*legend,r'\end{tabular}}\par\vspace{.7em}',r'\begin{tikzpicture}',r'\begin{groupplot}[group style={group size=2 by '+str(rows)+r',horizontal sep=1.50cm,vertical sep=1.65cm},width=.45\textwidth,height='+h+r',grid=major,grid style={gray!20},tick label style={font=\scriptsize},label style={font=\small},title style={font=\small},scaled y ticks=false,yticklabel style={/pgf/number format/fixed,/pgf/number format/precision=3},unbounded coords=jump]']
 for p in ps:
  opts=['title={'+esc(p['title'])+'}','xlabel={'+esc(p['xlabel'])+'}','ylabel={'+p['ylabel']+'}']
  if p.get('xscale')=='log':opts+=['xmode=log']
  if 'xlim' in p:opts += [f"xmin={p['xlim'][0]}",f"xmax={p['xlim'][1]}"]
  out.append(r'\nextgroupplot['+','.join(opts)+']')
  for c in p['curves']:out.append(r'\addplot[thick,'+style(c)+'] coordinates {'+coord(c)+'};')
 for _ in range(rows*2-len(ps)):out.append(r'\nextgroupplot[hide axis]')
 out += [r'\end{groupplot}\end{tikzpicture}',r'\caption{'+esc(f['note'])+r'}\label{fig:atlas-'+f['id']+'}',r'\end{figure}',r'\noindent{\footnotesize Export files: \code{'+f['id']+r'.svg} and \code{'+f['id']+r'.png}.\\ Directory: \code{aerodynamic-investigation/extended/figures/}.}']
 return '\n'.join(out)
def build_extended(root):
 R=root/'aerodynamic-investigation/extended';D=json.loads((R/'analysis-summary.json').read_text());F=json.loads((R/'figure-data.json').read_text());assert D['cases']==92 and not D['missing'] and len(F)==42
 panels=sum(len(f['panels']) for f in F);maxrough=max(x['max_abs_error'] for x in D['native_OR_roughness_verification'])
 out=[r'''
\clearpage\section{Extended coefficient study and plot atlas}\label{sec:extended}
\subsection{Completed experiments}
The follow-on studies have now been run. This extension adds 67 new RASAero Windows GUI configurations to the previous 25, for 92 total. All configurations are evaluated at 300 Mach values from 0.01 to 3.00 and at 0, 2 and 4 degrees angle of attack, giving 82,800 matched coefficient points. A further 24 native OR finish sweeps verify the separate exact-roughness reconstruction. MIT OR application code and installed binaries remain unchanged.

The atlas contains \textbf{42 plot sheets with PANELS panels}, plus the earlier flight and component plots. Each sheet is also supplied as a standalone SVG and PNG. The local gallery groups them by investigation topic. The retained raw exports, common-state table and bandwise error metrics support replotting without repeating the simulations.

\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.12}
\caption{New configurations beyond the first 25-case study.}\label{tab:extendedmatrix}
\begin{tabularx}{\textwidth}{@{}L{.26\textwidth}Xr@{}}\toprule
Study & New variations & Cases\\\midrule
Nose geometry & Cone, von K\'arm\'an, ellipsoid at nose lengths 6, 12, 18 in; tangent-ogive lengths 8, 24 in & 11\\
Fin geometry & Intermediate sweep, span, taper, thickness, bevel distance and rounded profile & 21\\
Nozzle area & Diameter fractions 0.25, 0.50, 0.75 and 1.00, with and without fins & 7\\
Surface roughness & 1.27, 6.35, 30.48, 152.4 micrometers on Hbody, Hsq and Hbev & 12\\
Flow transition & Transitional-flow option on six H/S baseline geometries & 6\\
Normal-force option & Rogers Modified Barrowman on four finned baseline geometries & 4\\
Reynolds/scale & All external lengths multiplied by 0.5 and 2 on three H geometries & 6\\\bottomrule
\end{tabularx}\end{table}

All direct aerodynamic comparisons retain the same body frontal reference area, dimensions, nominal atmosphere and angle of attack. Roughness and nozzle cases require the explicit qualifications below. The original 25 cases are re-used from preserved RASAero exports and independently re-evaluated in OR at all three angles. These are deterministic model comparisons, not 82,800 independent physical experiments.

\subsection{Coefficient definitions and checks}
OR's stored drag term is not wind-axis drag at nonzero angle of attack. Its simulation applies axial force $C_A$ and normal force $C_N$ in rocket coordinates. We therefore compare the common wind-axis quantities
\begin{align}
 C_D&=C_A\cos\alpha+C_N\sin\alpha,\\
 C_L&=C_N\cos\alpha-C_A\sin\alpha.
\end{align}
The raw RASAero CD Power-Off column satisfies the first identity. For nonzero nozzle area, its single CL column satisfies the \emph{power-on} identity; coast lift is reconstructed using CA Power-Off. Thus the CL comparison uses power-off lift consistently. CP is distance from the nose tip divided by body diameter; no mass/CG is used. Normal-force slope is the same $C_N(4^\circ)/(4\pi/180)$ secant in both programs. OR warns that its body normal-force treatment has limitations above Mach 1.1; the supersonic coefficient comparisons are retained to show that limitation.
'''.replace('PANELS',str(panels))]
 out += [r'''
\clearpage\subsection{What the additional data establish}
\textbf{The supersonic nose issue is shape-specific.} At Mach 2 and nose L/D=3, the conical, von K\'arm\'an and ellipsoidal controls agree far more closely than the tangent ogive. This supports the earlier local-tail-slope diagnosis rather than an across-the-board error in reference area or body friction.
\begin{table}[H]\centering\small
\caption{Finless-body $C_D$ at Mach 2, nose length 12 in, diameter 4 in, total length 60 in.}
\begin{tabular}{@{}lrrr@{}}\toprule
Nose shape & MIT OR & RASAero & RAS minus OR\\\midrule
''']
 for x in D['findings']['nose_M2']:
  label={'Hbody':'Tangent ogive','Hbody-cone12':'Cone','Hbody-vk12':"von K\'arm\'an",'Hbody-ellipsoid12':'Ellipsoid'}[x['shape']]
  out.append(f"{label} & {x['or_cd']:.5f} & {x['ras_cd']:.5f} & {x['ras_minus_or']:+.5f}\\\\")
 out += [r'''
\bottomrule\end{tabular}\end{table}
The nose-shape curves also show that agreement at Mach 2 does not imply a correct transonic join. Several OR curves begin their rise earlier and spread it across a wider Mach interval; the RASAero rise is sharper. The atlas separates full-range and transonic behavior so the nose change is not evaluated solely on one supersonic point.

\textbf{Fin discrepancies depend on the full section and planform.} The thickness, sweep, span, taper and bevel-length sweeps test the earlier profile diagnosis on independent geometries. They retain large square-fin discrepancies and expose the attached/detached-shock changes in the MIT bevel branch. Rounded fins provide an additional profile control. Finless subtraction and geometric scale/length tests are plotted separately so an apparent improvement in total drag is not mistaken for agreement of each component.

\textbf{A physical roughness match does not eliminate the roughness-model difference.} RASAero's available values differ from OR's native enum values. Rather than call unlike values equivalent, the gray curves show native OR at the nearest available finish, while the blue exact-roughness curves evaluate the existing OR friction correlation at the RASAero numerical roughness. This reconstruction changes no installed code and reproduces all 24 retained native nonzero-finish sweeps to within $1.5\times10^{-12}$ in $C_D$.

For smooth-baseline friction $C_{D,f,0}$ and whole-body length $L$, the reconstruction is
\begin{equation}
 C_D(k)=C_D(0)+C_{D,f,0}\left[\frac{\max\{C_{f,0},\,0.032(k/L)^{0.2}f_R(M)\}}{C_{f,0}}-1\right],
\end{equation}
where $f_R$ is the installed OR roughness compressibility factor and $C_{f,0}$ its fully turbulent smooth coefficient. It preserves OR pressure/base terms. In the Hbody case at $k=30.48$ micrometers and Mach 0.3, OR's drag increase is 0.0453 versus 0.0305 in RASAero; at Mach 2 it is 0.0280 versus 0.0362. The residual is therefore not fixed by matching surface names or by one roughness multiplier.

\textbf{The net square-fin roughness response vanishes in RASAero over this matrix.} For every tested nonzero roughness and all 300 Mach values, the roughness-induced total-CD increment of Hsq equals that of Hbody within $2.1\times10^{-15}$. Thus the isolated square-fin contribution does not respond to roughness, while the beveled-fin contribution does. At Mach 0.3 and 30.48 micrometers, RASAero adds 0.0305 to both Hbody and Hsq but 0.0553 to Hbev. This is stronger evidence of a profile-conditional model structure than a total-drag comparison alone. It does not establish the correctness of that structure.

\textbf{Flow-transition responses differ in both magnitude and sign.} At Mach 0.3 the transition option changes Hsq drag by $-0.23402$ in RASAero versus $-0.01054$ in OR; for Hbev the changes are $-0.04922$ and $-0.01054$. At Mach 2, the OR option increases Hsq and Hbev drag by 0.02668, whereas RASAero decreases them by 0.00100 and 0.00567. The OR branch uses a different supersonic compressibility factor from its fully turbulent branch; the option is not guaranteed to reduce the resulting coefficient. The net-fin transition plots remove the body response and show where this dependency enters.

\textbf{The nozzle-sensitive term is area-proportional in these tests.} Sweeping nozzle/body diameter ratios 0.25, 0.50, 0.75 and 1.00 gives power-off/on coefficient differences proportional to nozzle area. The fitted reference is simply the observed full-area difference, not an assumed base-pressure law. The maximum coefficient residual is below $1.2\times10^{-15}$ over all Mach points for both the finless and square-finned families. OR does not implement the corresponding nozzle-area input in this aerodynamic fixture; its unchanged curve is shown as a missing dependency, not a matched powered-flow prediction. These data still do not identify the absolute unpowered body-base coefficient.
''']
 out += [r'''
\clearpage\subsection{Normal force, CP and interpretation limits}
The default RASAero Barrowman option omits subsonic body lift that OR includes. Enabling Rogers Modified Barrowman is therefore a meaningful separate normal-force comparison. It is not a substitute for the turbulent-flow option and does not change the geometric fin profile. The following table gives a common subsonic state; the atlas then tracks the behavior through Mach 3.
\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.12}
\caption{Normal force and CP at Mach 0.3 and angle of attack 4 degrees. CP below is in inches from the nose tip.}
\begin{tabular}{@{}llrrr@{}}\toprule
Case & Quantity & MIT OR & RAS default & RAS modified\\\midrule
''']
 for n in ['Hsq','Hbev','Ssq','Sbev']:
  v=D['findings'][n+'-rogers']
  out.append(f"{n} & $C_N$ & {v['CN4_M03_OR']:.4f} & {v['CN4_M03_RAS_default']:.4f} & {v['CN4_M03_RAS_modified']:.4f}\\\\")
  out.append(f" & CP [in] & {v['CP4_M03_OR_in']:.3f} & {v['CP4_M03_RAS_default_in']:.3f} & {v['CP4_M03_RAS_modified_in']:.3f}\\\\")
 out += [r'''
\bottomrule\end{tabular}\end{table}
For these four cases, OR lies between the default and modified RASAero normal-force predictions at Mach 0.3. The modified option therefore does not automatically improve agreement. It also moves the RASAero CP farther aft, while OR predicts a more forward CP. These are separate force/interference-model differences, not fin-profile export errors.

\textbf{Scope of inference.} The measurements here are outputs of two simulation programs, not wind-tunnel or flight measurements. The studies characterize predictor disagreement and isolate dependencies; they do not establish physical truth. The new cone/Haack/ellipsoid controls support a shape-specific nose correction. The roughness, transition and fin sweeps show why a single calibration constant is inadequate. Angle-of-attack results add independent force/CP differences that a zero-angle drag fit cannot correct.

No aerodynamic correction was installed in MIT OR. The earlier nose-term trial remains an offline diagnostic, valid only over its stated Mach interval. Replacing the production transonic or fin model still requires a justified correlation and external validation. The thin-fin extrapolation remains a model-limit diagnostic rather than a physical drag target.

\textbf{Numerical evidence and preservation.} Every OR row passes the component-sum check. RASAero output is split by angle of attack before interpolation, and force-axis identities are checked across all matched rows. Native OR roughness curves provide an independent check of the exact-roughness reconstruction. Hashes of the installed JAR and monitored source files are retained before/after the extension. The original flight study and 25-case investigation data remain intact. One RASAero session exited during the batch; the remaining cases were run after relaunch, with an independent baseline repeat used to check continuity.

\textbf{Data navigation.} The \code{aerodynamic-investigation/extended/} directory contains 92 native RASAero input files, the raw RASAero exports, the OR engine outputs, \code{matched-coefficients.csv}, \code{error-metrics.csv}, \code{axis-audit.csv}, and a plot gallery in \code{index.html}. \code{figure-data.json} retains the arrays used by both the SVG/PNG figures and this standalone LaTeX atlas. Plot coordinates are adaptively simplified with interpolation error below the greater of $10^{-6}$ or $10^{-3}$ of each curve range; global extrema and a Mach spacing no larger than 0.05 are retained. All numerical metrics use the full Mach grid.

The native GUI inputs follow the \href{https://www.rasaero.com/dloads/RASAero\%20II\%20Users\%20Manual.pdf}{RASAero II Users Manual}, especially nose/profile geometry, pp. 10--16; roughness, pp. 52--53; and modified-Barrowman/flow options, pp. 54--56. The actual installed MIT source supplies the OR formulas. No black-box RASAero component coefficient is mislabeled as a published internal equation.
''']
 out.append(r'\clearpage\subsection{Coefficient plot atlas}')
 out.append('The following sheets are grouped by mechanism. Blue dashed and orange solid normally denote MIT OR and RASAero; each sheet states its legend explicitly. Roughness reconstructions, nozzle comparisons and multi-angle plots have separately labeled lines.')
 # The first figure starts on the next page; this short navigation page includes an index.
 out.append(r'{\small\begin{longtable}{@{}rL{.84\textwidth}@{}}\toprule Sheet & Topic\\\midrule\endhead')
 for i,f in enumerate(F,1):out.append(str(i)+' & '+esc(f['title'])+r' (Fig.~\ref{fig:atlas-'+f['id']+r'})\\')
 out.append(r'\bottomrule\end{longtable}}')
 out.append(r'\definecolor{atlasgray}{HTML}{777777}')
 for f in F:out.append(figure(f))
 return '\n\n'.join(out)
