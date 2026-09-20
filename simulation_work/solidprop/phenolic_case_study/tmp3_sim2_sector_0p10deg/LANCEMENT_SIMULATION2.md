# Lancement de la Simulation 2

Cette copie est indépendante de `tmp3`. Elle conserve le maillage validé de la
Simulation 1 et ses huit couches radiales dans `phe0`.

## Ce qui est configuré

- `SVAR1` : conversion pyrolytique \(\alpha\) ;
- `SVAR2` : vitesse \(\dot{\alpha}\) ;
- `SVAR3` : source massique locale de gaz en \(\mathrm{kg\,m^{-3}\,s^{-1}}\) ;
- `SVAR4` : masse gazeuse cumulée par volume initial en
  \(\mathrm{kg\,m^{-3}}\) ;
- `SVAR5` : puits énergétique sensible des gaz en \(\mathrm{W\,kg^{-1}}\) ;
- correction de la convection chaude par soufflage ;
- récession énergétique avec \(H_\mathrm{eff}=35\ \mathrm{MJ\,kg^{-1}}\) ;
- suppression d'une couche seulement si
  \(\bar{\alpha}\geq0{,}99\), \(\alpha_\mathrm{min}\geq0{,}90\), et si la
  récession énergétique atteint sa face externe ;
- calcul distribué sur 10 cœurs ;
- durée de 7 s avec des macro-incréments de 0,05 s.

La convection externe à 8 \(\mathrm{W\,m^{-2}\,K^{-1}}\) et le rayonnement
externe restent inchangés.

## Lancement dans l'interface graphique

1. Sous Windows, double-cliquer sur `launch_simulation2_workbench.cmd`.
2. Vérifier que Workbench a ouvert le projet situé dans `tmp3_sim2`.
3. Ouvrir la cellule **Modèle** de l'analyse **Thermique transitoire**.
4. Dans l'arbre, vérifier la présence de :
   - `Simulation 2 - UserMatTh et outgassing` sous `phe0` ;
   - `Simulation 2 - soufflage et ablation` sous l'analyse.
5. Sélectionner le second objet et vérifier
   **Émettre la commande Solve / Issue Solve Command = Non**.
6. Ne pas modifier le nombre de couches ni les pas de temps pour ce premier
   calcul.
7. Cliquer sur **Résoudre** dans Mechanical.

Le contrôleur effectue lui-même la séquence
`SOLVE -> bilan gaz/énergie -> redémarrage multi-trame -> EKILL éventuel ->
déplacement de la convection`. Après le premier macro-pas, chaque `SOLVE`
reprend explicitement le dernier état convergé avec `ANTYPE,,REST,,,CONTINUE` :
la température et les SVAR ne sont donc plus recalculées depuis \(t=0\).

Le fichier `simulation2_history.csv` est écrit dans le répertoire du solveur.
Il est fermé et rouvert en mode ajout après chaque macro-pas afin que les
lignes déjà calculées restent disponibles même si le calcul est interrompu.
Les fichiers de redémarrage DMP restent séparés par rang ; il faut conserver
les mêmes 10 cœurs pendant toute la simulation.

## Vérifications déjà exécutées

- compilation et export x64 de `USERMATTH` : réussis, sans avertissement ;
- coupon matériau chaud : cinq SVAR non nulles et cohérentes ;
- preuve minimale de continuation : \(25\,^\circ\mathrm{C}\) à 0,05 s puis
  \(35\,^\circ\mathrm{C}\) à 0,10 s (et non \(40\,^\circ\mathrm{C}\), qui
  indiquerait un recalcul depuis zéro) ;
- coupon annulaire du contrôleur : trois load steps à 0,001, 0,002 et
  0,003 s, zéro erreur MAPDL et croissance continue de `SVAR1` ;
- répétition du coupon en mémoire distribuée sur 10 cœurs : zéro erreur,
  mêmes bilans `SSUM` et fichiers `.rnnn` produits pour chaque rang ;
- réouverture du projet sauvegardé : contrôleur multi-trame présent,
  `Issue Solve Command = False`, et les deux configurations de résolution
  sont persistées en DMP sur 10 cœurs.

Cette version à huit couches est un pilote de suppression. Une étude de
convergence avec davantage de couches radiales devra être menée après ce
premier calcul complet.
