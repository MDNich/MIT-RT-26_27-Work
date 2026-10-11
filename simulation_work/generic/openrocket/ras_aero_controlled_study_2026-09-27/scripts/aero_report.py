"""Embed the aerodynamic investigation in the existing standalone report."""
import csv,json
import numpy as np

def build_aero_section(root):
 R=root/'aerodynamic-investigation';D=json.loads((R/'analysis-results.json').read_text());a={}
 for n in ['Hbody','Sbody','Hsq','Hbev','Ssq','Sbev']:
  rr=[x for x in csv.DictReader((R/'rasaero'/f'{n}.csv').open()) if float(x['Alpha'])==0 and float(x['Mach'])<=3]
  oo=list(csv.DictReader((R/'openrocket'/f'{n}.csv').open()))
  a[n]={'m':np.array([float(x['mach']) for x in oo]),'o':np.array([float(x['cd']) for x in oo]),'r':np.array([float(x['CD']) for x in rr]),'np':np.array([float(x['nose_pressure']) for x in oo])}
 def coords(x,y):
  ix=np.arange(0,len(x),2);ix=np.unique(np.r_[ix,len(x)-1]);return ' '.join(f'({x[i]:.6g},{y[i]:.7g})' for i in ix if np.isfinite(y[i]))
 def plot(kind):
  out=[r'\begin{figure}[H]\centering\begin{tikzpicture}',r'\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.35cm},width=.455\textwidth,height=5.5cm,xmin=.1,xmax=3,xlabel={Mach},ylabel={$C_D$},grid=major,grid style={gray!20},tick label style={font=\small},title style={font=\small},legend style={font=\scriptsize,draw=none,fill=white,at={(.97,.97)},anchor=north east}]']
  for fam in ['H','S']:
   out.append(r'\nextgroupplot[title={'+('4 in' if fam=='H' else '2.26 in')+(' body' if kind=='nose' else ' net fin contribution')+'}]')
   if kind=='nose':
    d=a[fam+'body'];m=d['m'];p=(2 if fam=='H' else 1.13)/np.hypot((2 if fam=='H' else 1.13),(12 if fam=='H' else 10));q=np.full(len(m),np.nan);ok=m>=1.32;q[ok]=d['o'][ok]-d['np'][ok]+2.1*p*p+.5*p/np.sqrt(m[ok]**2-1)
    curves=[(d['r'],'burntorange','RAS'),(d['o'],'B','MIT OR'),(q,'g,dashed','Trial nose term')]
   else:
    m=a[fam+'body']['m'];curves=[]
    for profile,style in [('sq',''),('bev',',dashed')]:
     for solver,col in [('r','burntorange'),('o','B')]:curves.append((a[fam+profile][solver]-a[fam+'body'][solver],col+style,('RAS ' if solver=='r' else 'OR ')+('square' if profile=='sq' else 'bevel')))
   for y,col,lab in curves:
    out.append(r'\addplot[thick,'+col+'] coordinates {'+coords(m,y)+'};');out.append(r'\addlegendentry{'+lab+'}')
  out.append(r'\end{groupplot}\end{tikzpicture}')
  cap=('An offline, unfitted nose-term substitution substantially closes the supersonic finless-body gap. The trial is defined only from Mach 1.32 upward and leaves original OR friction and base drag intact.' if kind=='nose' else 'Paired subtraction isolates the net effect of adding fins, including any fin/body interaction. RASAero does not expose a pressure/friction split; these are not isolated fin-pressure coefficients.')
  out.append(r'\caption{'+cap+r'}\end{figure}')
  return '\n'.join(out)
 out=[r'''
\clearpage\section{Aerodynamic investigation and proposed corrections}\label{sec:aero}
\subsection{Scope and controlled experiments}
The follow-on investigation evaluates 25 configurations in the Windows 11 RASAero II GUI and in the installed MIT OR aerodynamic engine. It contains 7,500 common Mach/configuration points: Mach 0.01--3.00 at increments of 0.01, zero angle of attack, sea level, smooth surfaces and fully turbulent flow. These are static aerodynamic sweeps; the new coefficients have not been used to claim new flight performance. No application source, installed JAR, or original rocket model was changed.

H denotes the 4 in rocket family and S the 2.26 in family from the flight study. ``sq'' means square fins, ``bev'' means a 0.25 in leading bevel with a blunt trailing edge, and ``body'' means the same nose/body with fins removed. The two bevel descriptions are MIT TRIANGULAR and RASAero Hexagonal Blunt Base. Chordwise bevel distance, maximum thickness and trailing-edge thickness agree.

\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.15}
\caption{Aerodynamic test matrix. All lengths below are in inches.}\label{tab:aeromatrix}
\begin{tabularx}{\textwidth}{@{}L{.26\textwidth}Xr@{}}\toprule
Family & Controlled variants & Cases\\\midrule
Baseline & Hsq, Hbev, Ssq, Sbev & 4\\
Finless & Hbody, Sbody & 2\\
Square thickness & H: 0.001, 0.0625, 0.25; S: 0.0625, 0.25 & 5\\
Fin sweep & Zero sweep on Hsq, Ssq, Hbev & 3\\
Beveled profile & H: thickness 0.001 and 0.25; bevel length 0.50 & 3\\
Body length & Hbody: 24 and 96; Hsq: 96 & 3\\
Fin count & Hsq: three fins instead of four & 1\\
Nose length & Hbody: 6 and 18, holding overall length at 60 & 2\\
Nozzle probe & Hbody and Sbody: nozzle diameter equal to body diameter & 2\\\bottomrule
\end{tabularx}\end{table}

\textbf{Input and extraction checks.} RASAero native files are explicit variants of the already matched MIT exports. Its Aero Plots CSV concatenates 0, 2 and 4 degree sweeps; only the 2,500 zero-angle rows are selected before interpolation to the 300 OR Mach points. At zero angle, the exported CD agrees with power-off CD. In the two nozzle probes only power-on CD changes. Full-size nozzles are coefficient diagnostics, not proposed motor hardware.

The OR fixture reads the same CDX dimensions into in-memory components, calls the installed aerodynamic calculator and verifies that the component coefficients sum to the total. It uses the actual exported body length (47.9999 in for H), not a rounded replacement. Mass, motor and recovery fields are irrelevant to these coefficient-only calculations. RASAero has a 1.2384\% larger body-length Reynolds number at the common nominal atmosphere; analytically matching this Reynolds number changes OR total $C_D$ by at most 0.000775 for $M\geq0.1$ across this suite. This cannot account for the observed discrepancies.
''']
 out += [r'''
\clearpage\subsection{Separate body drag from the net fin contribution}
For each geometry, define the measured finite difference
\begin{equation}
\Delta C_{D,\mathrm{fins}}=C_D(\mathrm{nose+body+fins})-C_D(\mathrm{nose+body}).
\end{equation}
It includes any body/fin interference or change in exposed body surface. No unsupported identification of this quantity with pure fin pressure drag is made.

\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.15}
\caption{Decomposition at Mach 0.30. Differences are RASAero minus MIT OR.}\label{tab:aerodecomp}
\begin{tabular}{@{}llrrr@{}}\toprule
Family & Contribution & MIT OR & RASAero & Difference\\\midrule
H & Finless body & 0.29586 & 0.24524 & $-0.05062$\\
H & Square fin addition & 0.08666 & 0.41220 & $+0.32555$\\
H & Beveled fin addition & 0.04274 & 0.12058 & $+0.07783$\\
S & Finless body & 0.37812 & 0.32453 & $-0.05359$\\
S & Square fin addition & 0.17333 & 0.65893 & $+0.48560$\\
S & Beveled fin addition & 0.07401 & 0.18311 & $+0.10910$\\\bottomrule
\end{tabular}\end{table}

The small total discrepancy for Hbev is a cancellation: a $-0.05062$ body difference plus a $+0.07783$ net-fin difference leaves only $+0.02722$. Its close subsonic flight agreement is therefore not evidence that each aerodynamic component is accurate. At Mach 0.8 the body differences are $-0.11084$ (H) and $-0.11216$ (S); at Mach 2 they reverse sign to $+0.11848$ and $+0.06843$.
''',plot('fin'),r'''
Fin-count scaling agrees in both programs: replacing four H fins with three changes the RASAero net contribution by the expected factor 0.75, with a maximum coefficient residual below $1.6\times10^{-7}$ over the full sweep. A fin-count convention error does not explain the gap.
''']
 out += [r'''
\clearpage\subsection{Tangent-ogive nose pressure: the strongest corrective lead}
The installed MIT engine returns only $C_{D,\mathrm{nose}}=0.000474$ for the H tangent ogive at Mach 2. Source inspection identifies the geometric input used in \code{SymmetricComponentCalc}: the slope is estimated over the last one percent of nose length,
\begin{equation}
 s_{\mathrm{tail}}=\frac{R-r(0.99L_n)}{\sqrt{[R-r(0.99L_n)]^2+(0.01L_n)^2}}.
\end{equation}
That value approaches zero for a nose tangent to its cylindrical body. The ogive branch then feeds it into a cone-like supersonic pressure formula. The H value is approximately 0.001622, whereas the radius/length equivalent-cone sine is 0.164399. This explains the near-zero pressure term and its very weak sensitivity to nose fineness. At Mach 2, shortening the H nose from 12 to 6 in raises RASAero body $C_D$ from 0.33796 to 0.60324; OR changes only from 0.21948 to 0.22346.

\textbf{Offline trial, with no fitted constants.} As a diagnostic, retain OR friction and base drag, replace only the ogive pressure term, and evaluate the existing supersonic functional form using the overall cone angle:
\begin{align}
 s_*&=\frac{R}{\sqrt{L_n^2+R^2}},\\
 \widehat C_{D,n}&=2.1s_*^2+\frac{0.5s_*}{\sqrt{M^2-1}},\quad M\geq1.32,\\
 \widehat C_D&=C_{D,\mathrm{OR}}-C_{D,n,\mathrm{OR}}+\widehat C_{D,n}.
\end{align}
This is a post-processing hypothesis, not an installed patch or an experimentally validated ogive model. It does not use a RASAero coefficient in its calculation. No claim is made for its extension through Mach 1.

\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.12}
\caption{Nose-only trial on six finless geometries, 169 Mach points each, 1.32--3.00. MAPE uses RASAero as denominator.}\label{tab:nosetrial}
\begin{tabular}{@{}lrrrr@{}}\toprule
 & \multicolumn{2}{c}{Mean absolute $C_D$ error} & \multicolumn{2}{c}{Mean absolute error [\%]}\\
Geometry & Original & Trial & Original & Trial\\\midrule
''']
 for d in D['nose_proposal']:
  name=d['case'].replace('Hbody','H').replace('Sbody','S')
  out.append(f"{name} & {d['baseline_mae']:.5f} & {d['candidate_mae']:.5f} & {d['baseline_mape_pct']:.2f} & {d['candidate_mape_pct']:.2f}\\\\")
 out += [r'''
\bottomrule\end{tabular}\end{table}
The aggregate mean absolute coefficient error falls from 0.14244 to 0.02308 (83.8\%). The stubby 6 in nose still has 12.66\% mean error, so this simple trial is not a general replacement model. A dedicated tangent/secant-ogive wave-drag treatment, with a separately validated transonic join, is the preferred improvement.
''',r'\clearpage',plot('nose'),r'''
\subsection{Fin profile, thickness and sweep}
The square-to-beveled change provides a strong profile diagnostic at identical planform and fin count. At Mach 0.3, the H total-coefficient reduction is 0.29163 in RASAero versus 0.04391 in OR, a factor of 6.64. At Mach 2, OR gives the same $C_D=0.32266$ for Hsq and Hbev, while RASAero gives 0.58680 and 0.48648 respectively. Body drag cancels in these comparisons.

In \code{FinSetCalc}, the MIT triangular branch uses leading-edge-normal Mach, a weak attached wedge-shock calculation, and a fallback to the square-edge stagnation coefficient when no attached solution is found. That fallback produces identical square/bevel fin pressure coefficients over Mach 1.75--2.49 for H and 1.56--2.22 for S in this sweep. This loss of profile sensitivity is an implementation mechanism, not a mismatched RASAero airfoil selection. Even doubling H bevel length from 0.25 to 0.50 in leaves the OR total unchanged at Mach 2 (0.32266), while RASAero decreases from 0.48648 to 0.44915.

\textbf{Proposed direction.} Replace the all-or-nothing detached-shock fallback with a finite-thickness fin model that retains section geometry in attached, detached and transonic regimes. Check the coordinate projection consistently: with chordwise bevel distance $b$ and leading-edge sweep $\Lambda$, the normal-section distance is $b\cos\Lambda$, so the normal wedge angle is $\tan^{-1}[t/(2b\cos\Lambda)]$. The present source uses the chordwise angle with normal Mach. This is a geometric consistency item to investigate, not a tested standalone correction. A normal-section wedge alone also does not account for the complete finite fin and its expansion/base regions.

Use independent sweep/profile fixtures as acceptance cases. At Mach 0.8, removing H square-fin sweep increases total $C_D$ by 0.03781 in RASAero and 0.07748 in OR. For H beveled fins the increases are 0.01027 and 0.06198. Increasing one constant drag multiplier would not reproduce both responses.
''']
 out += [r'''
\clearpage\subsection{Friction, base drag and limits of matching RASAero}
\textbf{Fin-local Reynolds number is supported by a length-invariance test.} OR computes one turbulent skin-friction coefficient from the entire aerodynamic rocket length and applies it to the fins. Lengthening the H body from 48 to 96 in leaves the RASAero net square-fin addition unchanged at Mach 0.3 (0.41220), while OR decreases it from 0.08666 to 0.08446. Evaluating the same OR correlation on fin mean aerodynamic chord removes that artificial body-length dependence in this isolated smooth-fin model.

The candidate uses $Re_f=V\bar c/\nu$ in the existing fin wetted-area expression,
\begin{equation}
 C_{D,f,\mathrm{friction}}=C_f(Re_f,M)\left(1+\frac{2t}{\bar c}\right)\frac{2NS_f}{A_{\mathrm{ref}}}.
\end{equation}
At Mach 0.3 it adds only 0.01515 (H) or 0.02504 (S) to OR $C_D$, compared with square-fin contribution gaps of 0.32555 and 0.48560. Thus it is a targeted structural improvement, not an explanation of the full discrepancy. Root boundary-layer interaction and roughness should be treated explicitly rather than inferred from a universal friction factor.

\textbf{Base-drag treatment needs a separate audit.} OR's body base term is $0.12+0.13M^2$ below Mach 1 and $0.25/M$ above it. The nearly common H/S subsonic body residual suggests a Mach-dependent body/base contribution rather than an overall geometry scale error. Changing the RASAero diagnostic nozzle diameter from zero to the full body diameter leaves power-off $C_D$ unchanged and produces the same power-off/on difference for H and S:
\begin{table}[H]\centering\small
\caption{Nozzle-sensitive drag contribution compared with OR's full body-base term. The two columns are different observables, not an asserted component identity.}
\begin{tabular}{@{}rrr@{}}\toprule
Mach & RAS full-nozzle $C_{D,off}-C_{D,on}$ & OR body-base $C_D$\\\midrule
0.30 & 0.05470 & 0.13170\\
0.80 & 0.07919 & 0.20320\\
1.00 & 0.13208 & 0.25000\\
1.20 & 0.14780 & 0.20833\\
2.00 & 0.14894 & 0.12500\\
3.00 & 0.12360 & 0.08333\\\bottomrule
\end{tabular}\end{table}
The export does not establish that a full nozzle removes every base-pressure effect, so the difference is not used as an absolute RASAero base coefficient. A future model should separate body base drag, fin trailing-edge drag and powered nozzle/plume effects; simply substituting this difference into OR would be unjustified. The primary flight-study nozzles remain zero.

\textbf{RASAero thin-fin behavior prevents blind calibration.} For H thickness 0.001 in at Mach 0.3, adding square fins changes RASAero $C_D$ by $-0.00149$, whereas the thin beveled profile adds $+0.07852$. OR gives $+0.02408$ and $+0.02372$. At ordinary square-fin thicknesses 0.0625, 0.125 and 0.25 in, RASAero's H net additions are 0.20369, 0.41220 and 0.82923: almost linear in thickness, despite unchanged planform area. The slender holdouts give the same qualitative result (0.32614, 0.65893, 1.32452). The near-zero-thickness cases are limiting diagnostics, not representative hardware. Their large profile-dependent offset, together with the unexposed RASAero component split, means an empirical fit could copy an extrapolation artifact. Do not remove finite-area skin friction merely to reproduce this limit.
''']
 out += [r'''
\clearpage\subsection{Ranked aerodynamic suggestions and validation gates}
\begin{table}[H]\centering\small\renewcommand{\arraystretch}{1.15}
\caption{Proposed aerodynamic work. None of these changes has been applied to MIT OR.}\label{tab:aerosuggestions}
\begin{tabularx}{\textwidth}{@{}L{.21\textwidth}XX@{}}\toprule
Priority & Proposed change and reason & Evidence required before adoption\\\midrule
1. Nose wave drag & Replace the near-zero tail-slope input with a shape-appropriate tangent/secant-ogive pressure model. The unfitted cone-angle trial closes most of the tested supersonic body gap. & Validate several nose fineness ratios, multiple shapes, and a continuous transonic join against measured drag, retaining the six-body sweep as regression data.\\
2. Fin pressure / profile & Preserve bevel and thickness sensitivity through detached-shock and transonic conditions. Audit sweep projection and finite-fin pressure/expansion treatment. & Match square/bevel differences, thickness trends and independent sweep cases; check the thin-fin limit and compare with primary fin data.\\
3. Fin friction & Give fins a physically appropriate local Reynolds length, with an explicit root-flow treatment rather than whole-rocket-length dependence. & Preserve invariance to upstream body length in the idealized case; validate both H/S planforms and roughness separately.\\
4. Base drag & Audit the Mach dependence of body and fin-base pressure and introduce an explicit powered-nozzle treatment if supported by data. & Use finless models and independently known nozzle-area/plume conditions; do not infer an absolute base coefficient from the present power-on/off difference alone.\\
5. Component diagnostics & Expose nose pressure, body/fin friction, fin pressure, body base and fin-base terms as separate outputs with reference areas. & Require summed components to equal total drag; retain Mach, Reynolds number, angle of attack and flow settings with every output.\\\bottomrule
\end{tabularx}\end{table}

\textbf{Do not use a universal $C_D$ multiplier.} Body residuals change sign with Mach; fin-profile effects depend on thickness and sweep; and existing subsonic bevel agreement includes cancellation. Fixing only one component can temporarily worsen total agreement. A calibration should be evaluated on geometries and Mach ranges excluded from any fitting and should retain a measured-data benchmark. The present work establishes differences between predictors, not which predictor is correct in every regime.

\textbf{Validation boundary.} The trial nose replacement is tested only at Mach 1.32--3 and does not validate transonic or subsonic flight improvement. In particular the heavy H flight cases never approach its validity range; their dominant target remains the fin/body subsonic balance. The 25-case sweeps exclude roughness, angle-of-attack drag, lugs, boattails, multistaging and active control. The original demonstrator is not used to infer clean component corrections because its description is more complex. No new apogee result is claimed from the offline coefficient trial.

\subsection{Evidence, references and reproduction}
All new fixtures, raw Windows exports, screenshots and matched coefficient tables are retained under \code{aerodynamic-investigation/}. The 25-entry \code{cases.json} records each variation. \code{matched-coefficients.csv} has all 7,500 matched rows; \code{analysis-results.json} includes extraction checks and trial-error statistics. \code{scripts/AeroSweep.java} calls the installed MIT engine; \code{scripts/analyze_aerodynamics.py} implements only analysis and the independent trial. The GUI export helper and its logs are retained with the study. These helpers are research fixtures, not modifications to OR.

The source audit used the local MIT implementations \code{SymmetricComponentCalc.java} (nose geometry and pressure), \code{FinSetCalc.java} (profile/sweep/friction), and \code{BarrowmanCalculator.java} (Reynolds number and base drag). The installed JAR and the seven files fingerprinted before this investigation were rechecked afterward. The preserved JAR SHA-256 is unchanged.

RASAero geometry and nozzle-input conventions are documented in the \href{https://www.rasaero.com/dloads/RASAero\%20II\%20Users\%20Manual.pdf}{RASAero II Users Manual}, pp. 14--16 and 84. The \href{https://openrocket.info/documentation.html}{OpenRocket technical documentation}, sections 3.4.2--3.4.5, gives the original skin-friction and pressure/base framework. The actual MIT source and measured program outputs take precedence when the custom triangular-fin branch differs from the historical documentation. No proprietary RASAero internal component equations are claimed from these black-box experiments.
''']
 return '\n\n'.join(out)
