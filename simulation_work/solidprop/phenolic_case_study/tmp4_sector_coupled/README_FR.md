# Simulation 4 — secteur phénolique avec consommation du char couplée

**Préparation uniquement. Aucun calcul transitoire lancé.**

Cette itération indépendante reprend la géométrie et le maillage de la simulation 3.
Elle est destinée à comparer les changements de modèle, pas à prédire une durée
de vie qualifiée. Les anciens dossiers et résultats ne sont pas modifiés.

## Fichiers et lancement volontaire

- Dossier Mac : `phenolic_case_study/tmp4_sector_coupled`.
- Copie autonome utilisée sous Windows : `C:\ansys_sector_iter4`.
- Paramètres : `config.json` ; contrôleur : `coupler.py`.
- Maillage, matériaux et contacts : `model_base.inp`.
- Entrée du calcul : `run_iteration4.inp` ; reprise : `resume_iteration4.inp`.
- Géométrie indépendante : `geometry/sector_0p10deg.step` et `.brep`.
- Sources de référence archivées : `source/`. Le `.wbpz` est le **modèle de
  maillage de référence**, pas un projet Workbench intégrant le nouveau contrôleur.

L'itération 4 se lance en MAPDL autonome. Le bouton Solve de l'ancien projet
Workbench ne lance **pas** cette nouvelle itération.

Dans PowerShell, depuis le dossier Windows :

```powershell
# Vérifications de fichiers/configuration seulement : aucun processus MAPDL.
.\launch_iteration4.ps1

# Validation MAPDL du modèle et des charges, sans commande SOLVE.
.\launch_iteration4.ps1 -PreflightMapdl

# UNIQUEMENT sur instruction explicite de lancement :
.\launch_iteration4.ps1 -Run

# Pendant un calcul : demande de pause au prochain état accepté.
.\request_pause.ps1

# Après une pause propre et vérifiée :
.\launch_iteration4.ps1 -Run -Resume
```

La licence est exclusivement `1055@localhost`. Le calcul est prévu sur **10 rangs**.
Le lanceur refuse de démarrer si un processus ANSYS/MPI existe déjà ou si des
résultats d'un lancement précédent risquent d'être écrasés. Sans `-Run`, il ne
lance jamais la simulation. L'installation locale ANSYS 2026 R1 est nécessaire ;
aucun fichier d'un ancien calcul n'est lu pendant la nouvelle exécution.

## Les trois changements

### 1. Chauffage de la surface réellement exposée

Une carte explicite des couples `(élément, face)` définit les 200 faces de chacune
des 64 rangées radiales de `phe0`. Le contrôleur efface les anciennes charges puis
applique `SFE,CONV` sur la rangée encore vivante. Cela évite de dépendre d'une
sélection nodale incluant des éléments adjacents morts. C'est une correction
préventive de la méthode précédente, pas une preuve que ce mécanisme expliquait
à lui seul son refroidissement.

Après chaque intervalle convergé, la puissance convective réellement enregistrée
dans les résultats est comparée à `Σ h A (Tgaz − Tface)` ; un écart supérieur à
2 % arrête la continuation. La surface externe en aluminium conserve sa
convection et son rayonnement ambiant. Faces de coupe et extrémités axiales :
adiabatiques, comme dans le modèle secteur précédent.

### 2. Couplage thermique et bilans explicites

La convection entre dans le système thermique implicite. Le rayonnement et le
coût énergétique de consommation du char sont convertis en puissances nodales
sur les mêmes faces, calculées avec l'état convergé précédent :

`Pnodale = Prayonnement − H_eff × débit_char`.

Le refroidissement par ablation agit donc sur la température résolue ; il n'est
plus uniquement utilisé pour calculer une « récession virtuelle ». Les puits
de pyrolyse et de chauffage des gaz restent dans `UserMatTh` et ne sont pas
soustraits une deuxième fois à la surface. La correction de soufflage utilise
le débit de gaz de pyrolyse et le débit de carbone retiré au pas précédent.
Elle reste une fermeture effective, sans transport interne résolu des gaz.

Le journal sépare stockage thermique, sources volumiques, convection, rayonnement,
coût d'ablation, gaz produits, char consommé et masse résiduelle. Le résidu de
l'équation thermique discrète est contrôlé avec les sorties élémentaires
`NMISC 38–42` ; au-delà de 5 %, le contrôleur s'arrête. Ce contrôle doit notamment
confirmer, lors du premier calcul autorisé, la restitution des sources UserMatTh
dans cette version du solveur.

Les intégrales temporelles des puissances sont des quadratures de fin de
macro-pas : elles sont **approchées** si MAPDL effectue des sous-pas internes.
L'énergie sensible associée aux cellules dont la suppression est programmée
est estimée séparément par intégration de `cp(T)` à conversion figée. Il n'y a
pas de projection conservative de l'enthalpie lors d'un changement de maillage.
Le bilan discret contrôlé ne constitue donc pas une démonstration d'un bilan
thermochimique global exact au passage des suppressions.

### 3. Loi de consommation du char distincte de la pyrolyse

La pyrolyse transforme le matériau vierge en char et gaz ; elle ne supprime pas
automatiquement le solide. Le débit de consommation du char combine deux
résistances :

`jcin = jref exp[−E/R (1/T − 1/Tref)] × (p/pref × activité)^n`

`jlim = jtransport × (p/pref × activité)`

`jchar,potentiel = alpha × (1/jcin + 1/jlim)^−1`.

Ce débit est ensuite limité par le char disponible, par l'apport thermique
estimé après conduction, et par 20 % au maximum de la masse de char d'une
cellule par macro-pas. L'estimation conductive utilise le flux radial du pas
précédent (composante Z, adaptée au secteur de 0,1° centré sur +Z).

Une rangée est programmée pour désactivation lorsque sa masse solide restante,
après pyrolyse et consommation de char, est inférieure à 0,1 % de sa masse
initiale. Cette faible masse résiduelle est enregistrée explicitement. Une
suppression **programmée** et une suppression **effectivement appliquée dans
l'état résolu** sont deux colonnes différentes. La dernière rangée n'est pas
nécessairement désactivée si l'horizon final est atteint immédiatement après la
décision ; le calcul s'arrête également dès consommation de `phe0`, sans tenter
d'appliquer cette loi à l'époxy ou aux autres matériaux.

La masse de char consommée est soustraite du bilan physique immédiatement,
mais sa contribution aux propriétés EF reste présente jusqu'à la désactivation
de la rangée entière. Cette approximation sous-maille est tracée dans
`subcell_mass_still_in_FE_kg`. Une étude de raffinement spatial et temporel reste
nécessaire, ainsi qu'une étude du critère de suppression collective si la surface
devient non uniforme axialement ou azimutalement.

## Hypothèses — pression et gaz inconnus

L'information fournie est **AP (perchlorate d'ammonium)**. C'est l'oxydant ; elle
ne donne ni le liant/combustible complet, ni les fractions de H₂O, CO₂, O₂ ou
d'autres produits, ni la pression de chambre. Aucune composition n'a été déduite.

`pressure_Pa` reste **null**. Le rapport de pression exploratoire vaut 1 : il
s'agit d'une normalisation numérique, **pas d'une pression de chambre fixée à
1 bar**. Les paramètres suivants sont des hypothèses de démonstration, non
des constantes cinétiques mesurées pour ce moteur :

| Paramètre exploratoire | Valeur |
|---|---:|
| Température de référence de la loi char | 1500 K |
| Flux cinétique de référence | 0,01 kg·m⁻²·s⁻¹ |
| Énergie d'activation | 100 kJ·mol⁻¹ |
| Exposant de pression | 0,5 |
| Limite de transfert de masse normalisée | 0,05 kg·m⁻²·s⁻¹ |
| Coût endothermique effectif de retrait | 35 MJ·kg⁻¹ |

Le coût effectif inclut une chimie non résolue ; il ne représente pas une
enthalpie de réaction spécifique et ne modélise pas une oxydation exothermique.
Un mode paramétrable `species` existe, mais exige une pression explicite et
les fractions et coefficients de chaque canal H₂O/CO₂/O₂. Il ne remplace pas
un calcul d'équilibre ni un mécanisme chimique détaillé.

Le rayonnement chaud est implémenté mais son émissivité effective vaut 0 par
défaut, faute de données. Température des gaz et coefficient convectif restent
les valeurs du cas précédent : 2230,85 °C et 1000 W·m⁻²·K⁻¹ avant correction de
soufflage. Ils ne sont pas recalculés à partir de l'AP.

Les densités de référence du modèle de pyrolyse sont désormais constantes
(vierge 1250, char 600 kg·m⁻³). Cela ferme le bilan gaz/solide sur le maillage
fixe, sans attribuer à la température une perte de masse sans gaz associé.
Conductivité, capacité thermique, cinétique de pyrolyse et DLL sont reprises du
modèle précédent ; les propriétés modifiées sont passées à la DLL par APDL.

## Géométrie, maillage, durée

| Grandeur | Valeur |
|---|---:|
| Angle du secteur / longueur axiale | 0,1° / 50 mm |
| Rayon intérieur / rayon extérieur | 66,675 / 76,2 mm |
| Épaisseur `phe0` | 1,270 mm |
| Époxy / `phe1` / aluminium | 0,3175 / 3,175 / 4,7625 mm |
| Rangées radiales `phe0` / époxy / `phe1` / aluminium | 64 / 16 / 64 / 32 |
| Divisions angulaires / axiales | 2 / 100 |
| Nœuds / éléments solides SOLID278 | 54 540 / 35 200 |
| Éléments `phe0` / éléments par rangée | 12 800 / 200 |
| Pas radial dans `phe0` | 19,84375 µm |
| Nœuds sur une surface radiale exposée | 303 |

Horizon initial : **7 s**, pour une comparaison avec la simulation 3 ; macro-pas
0,025 s, sous-pas internes autorisés jusqu'à 0,0001 s. L'intégration thermique
est d'ordre un implicite ; le couplage char/rayonnement est explicite entre
macro-pas. Une variation de température de face supérieure à 50 K sur un
macro-pas déclenche un avertissement de raffinement. L'ancienne extrapolation
de consommation complète en 20–30 s ne qualifie pas cette nouvelle loi.

## Contrôles et reprise

`validation/unit_tests.json` résume les tests Python sur données synthétiques.
`validation/mapdl_preflight.json` résume la vérification native des 64 surfaces
successivement exposées. Les empreintes SHA-256 des entrées sont dans
`validation/input_manifest.json`. Les entrées ne doivent plus changer une fois
le calcul initialisé.

Les tests sans SOLVE ne valident **ni la convergence thermique, ni l'exécution
effective de la DLL, ni une reprise réelle sur 10 rangs**. Ces points seront à
contrôler sur les premiers intervalles d'un lancement ultérieurement autorisé.

Pendant le calcul, les résultats seront dans `C:\ansys_sector_iter4` :
`solve_YYYYMMDD_HHMMSS.out`, `file*.err`, `simulation4_history.csv`, `state.json`
et `checkpoints/`. Les quatre dernières générations de restart distribuées
sont conservées, avec un état du contrôleur archivé à chaque macro-pas accepté.
Une demande de pause attend la convergence, l'export et la validation du
macro-pas en cours ; elle n'interrompt pas les écritures. Une panne n'est pas
une pause propre : le lanceur refuse sa reprise automatique et préserve les
fichiers pour examen. Aucune relance automatique ni tâche planifiée n'est créée.

## Références de l'interface solveur

- [SOLID278, faces et sorties de bilan énergétique, ANSYS 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_elem/Hlp_E_SOLID278.html).
- [ANTYPE, continuation multiframe, ANSYS 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_ANTYPE.html).
- [TINTP, intégration thermique, ANSYS 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_TINTP.html).
- [RESCONTROL, conservation des checkpoints](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/ans_cmd/Hlp_C_RESCONTROL.html).

Ces références documentent l'interface ANSYS ; elles ne fournissent pas les
coefficients exploratoires de consommation du char retenus ici.
