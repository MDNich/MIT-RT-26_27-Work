from pull_paths import *
import numpy as np,json
D=P/'output/latex/battery_side_pull'
case='friction_locked_fine';C=S/'runtime'/case
if not (C/'ACCEPTED.json').exists():raise SystemExit(0)
labels=[('friction_locked','Coarse mesh'),('friction_locked_fine','Fine mesh')]
tex=r'''\begin{tikzpicture}\begin{axis}[width=.98\linewidth,height=56mm,xlabel={Battery centre displacement (mm)},ylabel={Normal platen reaction (N)},xmin=0,xmax=.5,grid=both,legend style={font=\footnotesize,at={(.03,.97)},anchor=north west},xticklabel style={/pgf/number format/fixed,/pgf/number format/precision=2},tick label style={font=\small},label style={font=\small}]
'''
for i,(k,lab) in enumerate(labels):
 cfg=json.loads((S/'runtime'/k/'config.json').read_text());h=np.genfromtxt(S/'runtime'/k/'history.csv',delimiter=',',names=True);c=np.genfromtxt(S/'runtime'/k/'contact_history.csv',delimiter=',',names=True)
 mask=c['time']>=2
 np.savetxt(D/'data'/f'{k}_clamp.csv',np.column_stack([abs(h['ux_mm'][mask]),c['washer1_RFz'][mask],c['washer2_RFz'][mask]]),delimiter=',',header='u,washer1,washer2',comments='')
 color=['Teal','Navy'][i]
 tex+=r'\addplot+[color='+color+r',thick,mark=none] table[col sep=comma,x=u,y=washer1] {data/'+k+r'_clamp.csv};\addlegendentry{'+lab+'}\n'
tex+='\\end{axis}\\end{tikzpicture}\n';(D/'plots/ClampForces.tex').write_text(tex)
a=np.genfromtxt(C/'contact_detail.csv',delimiter=',',names=True);audit=json.loads((C/'ACCEPTED.json').read_text())
page=r'''\clearpage\PageTitle{Contact localization and clamp reactions}
\begin{center}\includegraphics[width=.76\linewidth,height=102mm,keepaspectratio]{figures/friction_locked_fine_plastic_plan.png}
\captionof{figure}{Refined 750 N contact model at $u_X=+0.5$ mm. The lower nickel flat leg is shown in deformed coordinates at scale 1:1. Colour is the maximum of top/bottom shell element-summary plastic strain, not a fracture index.}\end{center}
\begin{center}\input{plots/ClampForces.tex}
\captionof{figure}{Normal reaction at the first lower platen during the pull; the second platen gives essentially the same result. Both start at 750 N after the force-to-lock transfer. The fixed platen separation permits reaction to change under bending.}\end{center}
'''
page+=f"The refined contact calculation reports a maximum element-averaged penetration of {max(a['max_pen_mm'])*1000:.3f} micrometres ({max(a['max_pen_mm'])/.15*100:.3f}\\% of strip thickness) over its saved history. "
page+=f"The greatest accumulated plastic slip among the exported contact corner values is {max(a['max_plastic_slip_mm'])*1000:.3f} micrometres. These contact quantities use a different sampling convention from the element-averaged sliding in the main table.\\par\n"
page+=r'''The pressure and sliding depend on the assumed friction coefficient, contact stiffness and rigid support idealization. Their numerical convergence and constitutive calibration are distinct questions. Small penetration is a numerical contact check; it does not establish that the real nickel, washer or PCB avoids indentation or tearing.
'''
(D/'contact_page.tex').write_text(page)
print('contact appendix ready')
