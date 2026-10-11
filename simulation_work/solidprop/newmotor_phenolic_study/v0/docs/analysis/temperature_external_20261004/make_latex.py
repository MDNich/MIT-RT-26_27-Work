"""Generate a self-contained PGFPlots document from auditable analysis JSON."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[6]
OUT=REPO/'output/pdf'
OUT.mkdir(parents=True,exist_ok=True)
obs=json.loads((HERE/'temperature_history.json').read_text())
fit=json.loads((HERE/'fit_all.json').read_text())
validation=json.loads((HERE/'fit_validation.json').read_text())
central=json.loads((HERE/'forecast_central.json').read_text())
names=['half_dt','quarter_macro','double_mesh','quad_mesh','internal_2','internal_4']
variants={name:json.loads((HERE/f'forecast_{name}.json').read_text()) for name in names}

def f(v,n=1):return f'{v:.{n}f}'.replace('.',',')
def coords(rows,x,y,stride=1):
    subset=rows[::stride]
    if subset[-1] is not rows[-1]:subset.append(rows[-1])
    return '\n'.join(f'({r[x]:.8f},{r[y]:.8f})' for r in subset)

def plot(style,rows,y,stride=1):
    return r'\addplot['+style+'] coordinates {\n'+coords(rows,'time_s',y,stride)+'\n};\n'

holdout=[x for x in validation['comparisons'] if x['time_s']>5+1e-8]
maxout=max(abs(x['outer_error_K']) for x in holdout)
maxint=max(abs(x['interface_error_K']) for x in holdout)
maxprofile=max(x['profile_rmse_K'] for x in holdout)
maxalpha=max(x['alpha_rmse'] for x in holdout)
parameters=fit['fit']['parameters']
milestones=central['milestones']
rows=[];ranges=[]
for i,m in enumerate(milestones):
    rows.append(f"{int(m['fraction']*100)}\\,\\% & {f(m['time_s'])} & {f(m['outer_C'])} & {f(m['interface_C'])} & {f(m['remaining_mm'],3)} \\\\")
    tests=[m]+[v['milestones'][i] for v in variants.values()]
    vals={key:(min(t[key] for t in tests),max(t[key] for t in tests)) for key in ['time_s','outer_C','remaining_mm']}
    ranges.append(f"{int(m['fraction']*100)}\\,\\% & {f(vals['time_s'][0])}--{f(vals['time_s'][1])} & {f(vals['outer_C'][0],0)}--{f(vals['outer_C'][1],0)} & {f(vals['remaining_mm'][0],2)}--{f(vals['remaining_mm'][1],2)} \\\\")

observed_plot=plot('blue,line width=1.1pt',obs['points'],'outer_max_C',2)
observed_plot+=r'\addlegendentry{Extérieur de l\textquotesingle aluminium}'+'\n'
observed_plot+=plot('orange,line width=1pt',obs['points'],'interface_max_C',2)
observed_plot+=r'\addlegendentry{Interface phénolique/aluminium}'+'\n'
observed_plot+=plot('green,densely dashed,line width=.9pt',validation['history'],'outer_C')
observed_plot+=r'\addlegendentry{Modèle 1D, calage arrêté à 5 s}'+'\n'

projection=''
for name in names:
    projection+=plot('gray!45,line width=.5pt,forget plot',variants[name]['history'],'outer_C',25)
projection+=plot('blue,line width=1.2pt,forget plot',obs['points'],'outer_max_C',5)
projection+=plot('blue,dashed,line width=1.2pt',central['history'],'outer_C',12)
projection+=r'\addlegendentry{Extérieur aluminium : scénario ajusté}'+'\n'
projection+=plot('orange,dashdotted,line width=.9pt',central['history'],'interface_C',12)
projection+=r'\addlegendentry{Interface phénolique/aluminium}'+'\n'
projection+=r'\addlegendimage{gray!55,line width=.7pt}\addlegendentry{Variantes numériques (non probabilistes)}'+'\n'
for m in milestones:
    t=m['time_s'];y=m['outer_C'];pct=int(m['fraction']*100)
    projection+=f'\\draw[densely dotted,black!50] (axis cs:{t},22) -- (axis cs:{t},{y});\n'
    projection+=f'\\addplot[only marks,mark=*,mark size=2.2pt,blue,forget plot] coordinates {{({t},{y})}};\n'
    anchor='north west' if pct==25 else 'south east'
    label_x,label_y=(t+.6,25) if pct==25 else (t,y+9)
    projection+=f'\\node[anchor={anchor},font=\\small,fill=white,inner sep=2pt] at (axis cs:{label_x},{label_y}) {{{pct}\\,\\% : {f(t)} s / {f(y,0)} \\textdegree C}};\n'

tex=r'''\documentclass[10pt,a4paper]{article}
\usepackage[margin=16mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{textcomp}
\usepackage{amsmath,amssymb,booktabs,array}
\usepackage{xcolor,tikz,pgfplots}
\usepackage[hidelinks]{hyperref}
\pgfplotsset{compat=1.18}
\definecolor{blue}{HTML}{08357E}
\definecolor{orange}{HTML}{A04A00}
\definecolor{green}{HTML}{38761D}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\pagestyle{plain}
\pgfplotsset{every axis/.append style={grid=major,grid style={black!10},
 axis line style={black!45},tick label style={font=\small},label style={font=\small},
 legend style={font=\footnotesize,draw=none,fill=white},
 /pgf/number format/use comma,/pgf/number format/1000 sep={\,},scaled ticks=false}}
\begin{document}
{\Large\bfseries\color{blue} Température externe du moteur}\hfill{\small 4 octobre 2026}

{\large Historique ANSYS et extrapolation thermique 1D à paroi évolutive}

\textbf{Observation :} à 6,4125 s, l'extérieur de l'aluminium est à
\textbf{22,601 \textdegree C}, et son interface avec le phénolique à
\textbf{22,689 \textdegree C}. Température initiale et ambiante : 22 \textdegree C.

\begin{center}
\begin{tikzpicture}
\begin{axis}[width=17.4cm,height=5.2cm,xmin=0,xmax=6.65,ymin=21.98,ymax=22.82,
 xlabel={Temps physique (s)},ylabel={Température (\textdegree C)},
 title={\small\bfseries 1. Domaine calculé par ANSYS},
 legend style={at={(.02,.98)},anchor=north west},xtick={0,1,2,3,4,5,6}]
\fill[green!7] (axis cs:5,21.98) rectangle (axis cs:6.4125,22.82);
OBSERVED_PLOT
\node[font=\scriptsize,green!50!black,anchor=south] at (axis cs:5.72,22.01) {Test hors calage};
\end{axis}
\end{tikzpicture}

\vspace{1mm}
\begin{tikzpicture}
\begin{axis}[width=17.4cm,height=8.0cm,xmin=0,xmax=64,ymin=0,ymax=420,
 xlabel={Temps physique depuis l'allumage (s)},ylabel={Température (\textdegree C)},
 title={\small\bfseries 2. Chauffage prolongé : scénario 1D et sensibilité numérique},
 legend style={at={(.02,.98)},anchor=north west},xtick={0,10,20,30,40,50,60}]
\fill[blue!5] (axis cs:0,0) rectangle (axis cs:6.4125,420);
\draw[blue!50,densely dotted] (axis cs:6.4125,0) -- (axis cs:6.4125,420);
PROJECTION_PLOT
\node[font=\scriptsize,blue,rotate=90,anchor=center,fill=white,inner sep=1pt] at (axis cs:6.4125,230) {Fin ANSYS : 6,4125 s};
\end{axis}
\end{tikzpicture}
\end{center}
\vspace{-3mm}
\textbf{Scénario ajusté :} seuils de \emph{pyrolyse} de l'épaisseur initiale (\(\bar\alpha\geq0{,}98\)).
Les températures extrapolées ne sont pas des résultats ANSYS.

\begin{center}\small
\begin{tabular}{@{}r r r r r@{}}\toprule
Épaisseur pyrolysée & Temps (s) & Extérieur (\textdegree C) & Interface (\textdegree C) & Paroi restante (mm)\\\midrule
MILESTONE_ROWS
\bottomrule\end{tabular}\end{center}
\vspace{-1mm}
{\small\color{orange}\textbf{Exploratoire, non qualifié.} Le faible échauffement observé à 6,4 s ne justifie
pas une extrapolation linéaire. Ces courbes supposent le maintien du gaz chaud et des conditions du modèle v0.
Les tracés gris montrent une sensibilité numérique, pas un intervalle de confiance physique.}

\newpage
{\Large\bfseries\color{blue} Modèle, ajustement et limites}

\textbf{Ce qui diminue.} Le rayon intérieur \(a(t)\) augmente quand le charbon superficiel est consommé.
L'épaisseur géométrique restante vaut \(e(t)=R_i-a(t)\). Le front de pyrolyse se déplace également,
mais le matériau converti en charbon continue de conduire et de stocker la chaleur jusqu'à son élimination.
Les jalons 25/50/75 \% ne signifient donc \textbf{pas} 25/50/75 \% de paroi disparue.
À 6,4125 s : 0,595 mm pyrolysé, mais seulement 0,01984 mm retiré sur 4,7625 mm initialement.

\textbf{Géométrie et équations.} Conduction radiale cylindrique entre
\(a_0=66{,}675\) mm, \(R_i=71{,}4375\) mm et \(R_o=76{,}2\) mm.
L'aluminium est résolu comme une couche thermique, pas comme une température imposée.
Dans le phénolique :
\begin{align*}
\rho c_p\frac{\partial T}{\partial t}
 &=\frac1r\frac{\partial}{\partial r}\!\left(rk\frac{\partial T}{\partial r}\right)
 -\left[\rho L_p+(\rho_v-\rho_c)c_{p,g}(T_K-300)_+\right]\dot\alpha,\\[-1mm]
\dot\alpha&=333\exp\!\left(-\frac{64081}{R T_K}\right)(1-\alpha),\qquad
\rho=1250-650\alpha.
\end{align*}
Les conductivités et capacités calorifiques interpolent les tables vierge/charbon de v0 en fonction
de \(T\) et \(\alpha\). Continuité de température et de flux à l'interface, sans résistance de contact.
La limite chaude applique convection corrigée par le dégazage et puits d'ablation
\(H_{\rm eff}\dot m_c\); la consommation de charbon est limitée par sa cinétique,
l'énergie disponible et la masse produite. Les cellules sont retirées après épuisement,
avec le critère résiduel de v0 (0,1 \% de leur masse initiale).

\textbf{Conditions reprises de v0.} Gaz à 2230,85 \textdegree C ; convection nominale
1000 W\,m\(^{-2}\)\,K\(^{-1}\), réduite par le dégazage ; pression nominale 800 psi.
À l'extérieur : 22 \textdegree C, convection 8 W\,m\(^{-2}\)\,K\(^{-1}\), émissivité 0,25.
\(L_p=418\) kJ/kg, \(H_{\rm eff}=35\) MJ/kg, \(c_{p,g}=1600\) J/(kg\,K).
Aluminium : \(k=167\) W/(m\,K), \(\rho=2700\) kg/m\(^3\), \(c_p=896\) J/(kg\,K).

\textbf{Ajustement sur les données numériques.} 498 checkpoints acceptés ont été lus pour les
températures de surface ; 28 profils radiaux ont été extraits. La variation axiale/angulaire
échantillonnée est inférieure à \(4\times10^{-11}\) K, ce qui justifie ici la réduction 1D.
Le calage démarre sur le profil ANSYS à 0,35 s. Il minimise les écarts de température aux
profondeurs fixes, aux deux surfaces froides et à la face chaude, ainsi que les écarts de conversion.
Trois multiplicateurs proches de 1 sont ajustés :
\[
s_k=K_SCALE,\qquad s_c=CP_SCALE,\qquad \eta_q=Q_SCALE.
\]
Les deux premiers multiplient \(k\) et \(c_p\) du phénolique ; \(\eta_q\) corrige le flux conductif
du pas précédent utilisé dans la limite énergétique de consommation du charbon.
Ce dernier est un coefficient de fermeture du modèle réduit, \textbf{pas une propriété matériau}.
L'extrapolation repart du profil ANSYS accepté à 6,4125 s après réajustement sur tout l'historique.

\textbf{Vérification hors calage.} Ajustement seulement jusqu'à 5 s, puis prédiction libre jusqu'à
6,4125 s : erreurs maximales de OUT_ERR K à l'extérieur et INT_ERR K à l'interface ;
RMSE radiale maximale PROFILE_ERR K et RMSE de conversion maximale ALPHA_ERR.
Il s'agit d'une validation de reproduction d'ANSYS sur cet intervalle court, non d'une validation expérimentale.

\textbf{Sensibilité numérique non négligeable.} Référence : 240 cellules de phénolique + 64 d'aluminium,
éléments radiaux linéaires à deux points de Gauss, capacité consistante et Euler implicite ;
pas de couplage 0,0125 s. Tests à coefficients de calage inchangés : maillage multiplié par 2 et 4,
pas de couplage divisé par 2 et 4 ; séparément, 2 et 4 sous-pas thermiques par pas de couplage.
Les étendues obtenues à chaque jalon sont :
\begin{center}\small
\begin{tabular}{@{}r r r r@{}}\toprule
Pyrolyse & Temps (s) & Extérieur (\textdegree C) & Paroi restante (mm)\\\midrule
RANGE_ROWS
\bottomrule\end{tabular}\end{center}
Ces étendues ne constituent \textbf{ni des bornes garanties ni des intervalles statistiques}.
La dépendance au couplage explicite de l'ablation et à la suppression de cellules limite la convergence
à long terme ; le coefficient \(\eta_q\), calibré à la discrétisation de référence, ne doit pas être
assimilé à une loi physique indépendante du maillage. Les bilans discrets sont néanmoins fermés
(résidu relatif énergétique \(<8\times10^{-11}\), massique \(<10^{-14}\)).

{\small\color{orange}\textbf{Portée.} Les lois de pyrolyse/charbon de v0 restent exploratoires ; ni
l'érosion mécanique, ni une résistance de contact, ni une évolution réelle du débit/temps de combustion
ne sont identifiées par ces données. Le maintien du chauffage jusqu'à environ 50 s est une hypothèse,
pas une durée de combustion établie. Aucun calcul de résistance mécanique de l'aluminium n'est fourni.
Une simulation prolongée et des données matériau/essais sont nécessaires pour qualifier les prévisions.}

{\scriptsize\color{black!65} Traçabilité : étude \texttt{newmotor\_phenolic\_study/v0}, checkpoint 498,
\texttt{ansystmp/windows/checkpoints/state\_000498.json.gz}. Données, empreintes SHA-256,
ajustements et variantes : \texttt{docs/analysis/temperature\_external\_20261004/}.
Résultats de calcul, non mesures expérimentales. Analyse séparée : aucun fichier du runtime ANSYS modifié.}
\end{document}
'''
repl={'OBSERVED_PLOT':observed_plot,'PROJECTION_PLOT':projection,'MILESTONE_ROWS':'\n'.join(rows),
      'RANGE_ROWS':'\n'.join(ranges),'K_SCALE':f(parameters[0],6),'CP_SCALE':f(parameters[1],6),
      'Q_SCALE':f(parameters[2],6),'OUT_ERR':f(maxout,4),'INT_ERR':f(maxint,4),
      'PROFILE_ERR':f(maxprofile,3),'ALPHA_ERR':f(maxalpha,4)}
for k,v in repl.items():tex=tex.replace(k,v)
path=OUT/'newmotor_temperature_exterieure_1d.tex'
path.write_text(tex)
manifest={'latex':str(path),'latex_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in HERE.iterdir() if p.suffix in ('.json','.py') and p.name!='artifact_manifest.json'},
    'central_milestones':milestones,'qualification':'Exploratory, not physically validated'}
(HERE/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(path)
