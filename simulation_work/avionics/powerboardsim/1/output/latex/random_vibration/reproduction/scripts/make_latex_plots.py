from rv_paths import *
import csv,itertools,json
D=P/'output/latex/random_vibration';plotdir=D/'plots';datadir=D/'data'
plotdir.mkdir(exist_ok=True);datadir.mkdir(exist_ok=True)
(plotdir/'InputPSD.tex').write_text(r'''% Editable native PGFPlots figure. Four user-specified PSD points.
\begin{tikzpicture}
\begin{loglogaxis}[
 width=\linewidth,height=5.7cm,
 xmin=15,xmax=2600,ymin=0.02,ymax=0.22,
 xlabel={Frequency (Hz)},ylabel={PSD ($g^2$/Hz)},
 xtick={20,50,800,2000},xticklabels={20,50,800,2000},
 ytick={0.026,0.16},yticklabels={0.026,0.16},
 grid=both,major grid style={gray!25},minor grid style={gray!12},
 tick label style={font=\footnotesize},label style={font=\footnotesize},
 scaled ticks=false]
\addplot[color=Teal,line width=1.2pt,mark=*,mark size=1.6pt]
 coordinates {(20,0.026) (50,0.16) (800,0.16) (2000,0.026)};
\end{loglogaxis}
\end{tikzpicture}
''')
ma=json.loads((R/'modal_basis/audit.json').read_text())
for axis in 'XYZ':
 rows=list(csv.DictReader((R/'modal_basis'/('participation_'+axis+'.csv')).open()))
 vals=list(itertools.accumulate(float(r['fraction_of_total_mass'])*100 for r in rows))
 assert abs(vals[-1]-ma['effective_mass_fraction'][axis]*100)<1e-8
 with (datadir/('modal_mass_'+axis+'.csv')).open('w') as f:
  w=csv.writer(f);w.writerow(['frequency_hz','cumulative_mass_percent']);w.writerow([0,0])
  w.writerows((row['frequency_hz'],v) for row,v in zip(rows,vals));w.writerow([4000,vals[-1]])
s=r'''% Editable native PGFPlots figure. Data are plain numerical CSV files.
\begin{tikzpicture}
\begin{axis}[
 width=.985\linewidth,height=6.4cm,xmin=0,xmax=4000,ymin=0,ymax=100,
 xlabel={Frequency (Hz)},ylabel={Cumulative effective mass (\%)},
 xtick={0,500,1000,1500,2000,2500,3000,3500,4000},
 ytick={0,20,40,60,80,100},grid=major,grid style={gray!20},
 tick label style={font=\footnotesize},label style={font=\footnotesize},
 scaled ticks=false,legend pos=south east,
 legend style={font=\scriptsize,draw=gray!35,fill=white,cells={anchor=west}}]
\path[fill=Teal,fill opacity=0.08] (axis cs:20,0) rectangle (axis cs:2000,100);
\addlegendimage{area legend,draw=Teal!30,fill=Teal!8}
\addlegendentry{Input PSD range}
'''
for axis,color in [('X','orange!80!black'),('Y','Teal'),('Z','Navy')]:
 s+=r'\addplot[const plot,color='+color+r',line width=1pt] table[x=frequency_hz,y=cumulative_mass_percent,col sep=comma]{data/modal_mass_'+axis+'.csv};\n'
 s+=r'\addlegendentry{'+axis+f": {ma['effective_mass_fraction'][axis]*100:.2f}"+r'\% retained}'+'\n'
s+=r'\end{axis}'+'\n'+r'\end{tikzpicture}'+'\n'
(plotdir/'ModalEffectiveMass.tex').write_text(s)
print('Two editable LaTeX plots created with external numeric data for modal mass.')
