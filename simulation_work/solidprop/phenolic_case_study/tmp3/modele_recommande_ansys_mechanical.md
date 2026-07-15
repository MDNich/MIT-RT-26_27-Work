Modèle recommandé dans Mechanical
=================================

Ce guide décrit une méthode progressive pour modéliser l'échauffement, la pyrolyse puis la consommation de matière du moteur sans inclure le propergol dans la géométrie. Le modèle actuellement conservé dans Workbench est un système **Thermique transitoire** contenant quatre corps :

- `phe0` : phénolique intérieur, exposé aux gaz ;
- `epo` : couche d'époxy ;
- `phe1` : phénolique extérieur ;
- `alu` : enveloppe d'aluminium.

Les affectations de matériaux enregistrées sont maintenant cohérentes. La face chaude existante est `phe0_int` et la face extérieure de l'enveloppe est `alu_ext`.

## 1. Vérifier la transmission thermique entre les couches

Le simple fait que deux cylindres concentriques se touchent géométriquement ne garantit pas qu'ils échangent de la chaleur dans le modèle éléments finis. Il faut avoir l'une des deux configurations suivantes.

### Configuration A — Topologie partagée, recommandée

Les corps appartiennent à une même pièce multibody et les faces coïncidentes partagent les mêmes nœuds de maillage. Dans ce cas :

- aucun objet `Contact Region` n'est nécessaire ;
- le dossier `Contacts` peut rester vide ;
- la température est continue d'une couche à l'autre ;
- cette configuration est idéale si l'on suppose une liaison thermique parfaite.

À vérifier dans Geometry/DesignModeler :

1. Les quatre corps doivent appartenir à la même `Part`.
2. La topologie partagée doit être activée (`Share Topology`, `Form New Part` ou équivalent suivant l'éditeur géométrique).
3. Après génération du maillage, afficher une interface en masquant l'un des deux corps. Les nœuds des deux côtés doivent être superposés et communs, et non deux nappes de nœuds indépendantes.
4. Une coupe du maillage doit montrer des éléments raccordés sans décalage aux interfaces.

Un contrôle très simple consiste à faire une étude thermique provisoire avec une température imposée élevée sur `phe0_int` et une température faible sur `alu_ext`. Après résolution, la température doit évoluer continûment à travers toutes les couches. Une couche qui reste à la température initiale indique une interface non connectée.

### Configuration B — Corps séparés avec contacts thermiques

Si les maillages ne partagent pas leurs nœuds, créer trois contacts :

- `phe0_ext` $\equiv$ `epo_int` ;
- `epo_ext` $\equiv$ `phe1_int` ;
- `phe1_ext` $\equiv$ `alu_int`.

Dans `Connections`, utiliser des contacts `Bonded`. Pour une première simulation, une conductance thermique élevée ou `Program Controlled` permet d'approcher un contact parfait. Pour une étude plus réaliste, introduire une conductance de contact mesurée :

$$
q'' = h_c\,(T_1-T_2)
$$

où $h_c$ est la conductance thermique de contact en $\mathrm{W\,m^{-2}\,K^{-1}}$. Les interfaces collées phénolique–époxy et époxy–phénolique peuvent avoir une résistance thermique non négligeable, surtout en présence de porosités ou d'un décollement.

Ne pas créer simultanément une topologie partagée et des contacts thermiques sur la même interface : cela doublerait ou surcontraindrait la liaison.

## 2. Représenter les gaz de combustion sans modéliser le propergol

Le propergol n'a pas besoin d'être présent dans la géométrie pour une étude thermique unidirectionnelle. Son effet est représenté par le chargement de la paroi interne.

### Chargement recommandé : convection des gaz chauds

Dans l'arbre `Thermique transitoire` :

1. Clic droit sur l'analyse → `Insert` → `Convection`.
2. Affecter la convection à la sélection nommée `phe0_int`.
3. Définir la température des gaz $T_g(t)$ comme une table en fonction du temps.
4. Définir le coefficient de film $h(t)$ comme une table en fonction du temps.

Le flux reçu est alors calculé par Mechanical :

$$
q''_{conv}=h(t)\,[T_g(t)-T_s]
$$

Mechanical permet de définir séparément des tables temporelles pour la température ambiante et le coefficient de film : [documentation ANSYS 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/wb_sim/bc_tables_convection_load.html).

Si un calcul CFD ou un essai fournit déjà le flux net $q''(x,t)$, utiliser `Heat Flux` à la place de la convection. Ne pas imposer directement la température de la paroi égale à la température des gaz : une température imposée injecterait artificiellement toute l'énergie nécessaire pour maintenir cette valeur.

### Radiation interne

Si elle est significative, ajouter une condition `Radiation` sur `phe0_int` avec l'émissivité de la surface et une température radiative des gaz. Le terme correspondant est approximativement :


$$q''_{rad}=\varepsilon\sigma\left(T_{rad}^{4}-T_s^{4}\right)$$


Les températures de cette équation doivent être exprimées en kelvins.

### Conditions extérieures

Sur `alu_ext`, appliquer :

- une convection vers l'air ambiant ;
- éventuellement une radiation vers l'environnement ;
- aucune température imposée, sauf si elle représente réellement une condition expérimentale contrôlée.

## 3. Compléter les propriétés des matériaux

Les propriétés actuelles du phénolique sont définies jusqu'à 900 K et celles de l'époxy jusqu'à 600 K. Au-delà, les dernières valeurs tabulées sont conservées. Ces domaines doivent être étendus jusqu'aux températures réellement atteintes.

Pour chaque matériau, renseigner au minimum :

- masse volumique $\rho(T)$ ;
- conductivité thermique $k(T)$ ;
- chaleur spécifique $C_p(T)$ ou enthalpie $H(T)$ ;
- émissivité de la surface si la radiation est utilisée.

Pour l'aluminium, ajouter une représentation de la fusion si la température peut approcher son point de fusion. Pour l'époxy et le phénolique, utiliser des données propres aux résines et renforts réellement employés.

## 4. Modéliser d'abord la pyrolyse sans retirer d'éléments

Cette étape est recommandée avant toute simulation de récession géométrique.

Le phénolique vierge ne disparaît pas immédiatement quand il se pyrolyse. Il produit des gaz et laisse généralement une couche de char. Il faut donc distinguer :

1. le front de pyrolyse, où le matériau vierge se transforme ;
2. la couche de char restante ;
3. la surface de char éventuellement érodée ou oxydée.

### Méthode par capacité calorifique effective

Introduire l'énergie de pyrolyse sur un intervalle $[T_1,T_2]$ :

$$
C_{p,eff}(T)=C_p(T)+\frac{\Delta h_{pyr}}{T_2-T_1}
$$

où $\Delta h_{pyr}$ est l'enthalpie massique de pyrolyse. Cette augmentation de $C_p$ empêche la température de traverser la zone de décomposition sans consommer l'énergie correspondante.

Une définition directe de l'enthalpie $H(T)$ est préférable lorsqu'elle est disponible. MAPDL accepte une enthalpie dépendant de la température avec `TB,THERM,...,ENTH` : [propriétés thermiques ANSYS 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_mat/thermalmat.html).

### Résultats à extraire

Avant de retirer de la matière, vérifier :

- température de surface de `phe0_int` ;
- température maximale de l'époxy ;
- température maximale de l'aluminium ;
- température sur chaque interface ;
- profondeur de l'isotherme associée au début de pyrolyse ;
- temps nécessaire pour que le front atteigne l'époxy.

La masse transformée en produits gazeux peut être estimée par :

$$
m_{gaz}\approx \sum_{V_{pyr}}(\rho_{vierge}-\rho_{char})V_e
$$

Cette perte de masse n'implique pas nécessairement une récession égale au volume pyrolysé, puisque le char demeure en place.

## 5. Définir une loi de récession

Mechanical ne peut pas déduire une vitesse de consommation à partir de la seule température des gaz. Il faut fournir ou calibrer une loi. Une formulation énergétique simple est :

$$
\dot m''=\max\left(0,\frac{q''_{gaz}-q''_{cond}}{h_{abl}}\right)
$$

$$
\dot s=\frac{\dot m''}{\rho_s}
$$

avec :

- $q''_{gaz}=q''_{conv}+q''_{rad}$ ;
- $q''_{cond}$ : énergie conduite vers l'intérieur du solide ;
- $h_{abl}$ : enthalpie effective d'ablation, obtenue par essais ou littérature adaptée au matériau ;
- $\rho_s$ : masse volumique de la matière réellement retirée, généralement celle du char si la surface a déjà pyrolysé ;
- $\dot s$ : vitesse de récession normale à la surface.

Une autre possibilité est une loi empirique $\dot s=f(p,T_s)$, calibrée sur des essais de tir ou de torche. Ne pas utiliser automatiquement la loi de combustion du propergol comme loi d'ablation du phénolique : les mécanismes sont différents.

## 6. Représenter la consommation par désactivation progressive

L'objet `Element Birth and Death` est disponible en analyse thermique transitoire. Les éléments désactivés ne sont pas effacés géométriquement : leur conductivité est fortement réduite, leur capacité thermique et leur masse ne contribuent plus, et leurs charges sont annulées. Voir la [documentation Mechanical 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/wb_sim/ds_element_controls.html).

### Préparation géométrique recommandée

Découper le phénolique intérieur en bandes radiales sacrificielles :

- `AB01`, `AB02`, ..., de l'intérieur vers l'extérieur ;
- une vraie face géométrique entre deux bandes ;
- topologie partagée entre les bandes ;
- au moins un élément radial par bande ;
- une sélection nommée pour chaque bande et chaque future face chaude.

Les huit couches d'éléments actuelles donnent au maximum huit sauts de récession. Si seule une petite fraction de l'épaisseur doit être consommée, raffiner surtout la zone proche de `phe0_int`.

Une sélection purement élémentaire des huit couches existantes est possible, mais la gestion des nouvelles faces de convection est plus fragile. Les bandes géométriques sont plus faciles à vérifier et à réutiliser.

### Cas 1 — Vitesse de récession connue

Calculer l'instant de disparition de chaque bande par :

$$
\int_0^{t_i}\dot s(t)\,dt=\sum_{j=1}^{i}e_j
$$

où $e_j$ est l'épaisseur de la bande $j$.

Dans Mechanical :

1. Créer un load step pour chaque instant $t_i$.
2. Insérer un objet `Element Birth and Death` pour chaque bande.
3. Laisser la bande `Alive` avant $t_i$, puis la passer à `Dead`.
4. Créer une convection pour chacune des futures faces chaudes.
5. Activer la convection de la face courante uniquement pendant l'intervalle où cette face est exposée.

Ce déplacement du chargement est indispensable. Quand un élément est désactivé, sa convection et son flux surfacique sont également annulés. Si la convection reste attachée uniquement à `phe0_int`, l'échauffement peut s'arrêter artificiellement dès la disparition de la première bande.

### Cas 2 — Désactivation commandée par les résultats

Pour désactiver automatiquement les éléments ayant dépassé un critère, utiliser une boucle MAPDL :

1. résoudre un petit intervalle de temps ;
2. entrer dans `/POST1` et lire le dernier résultat ;
3. sélectionner seulement la bande actuellement exposée ;
4. construire une table des températures élémentaires ;
5. sélectionner les éléments dépassant le critère ;
6. reprendre l'analyse et appliquer `EKILL` ;
7. déplacer le chargement vers la nouvelle face ;
8. poursuivre jusqu'à la fin du tir.

Principe de sélection :

```apdl
/POST1
SET,LAST

CMSEL,S,AB_CURRENT,ELEM
ETABLE,TEL,TEMP
ESEL,R,ETAB,TEL,T_REC,1.0E30
CM,TO_KILL,ELEM

FINISH
/SOLU
ANTYPE,,REST
CMSEL,S,TO_KILL
EKILL,ALL
ALLSEL,ALL
```

`ETABLE,TEL,TEMP` fournit ici la température nodale moyenne par élément thermique. Une macro complète doit également traiter le cas d'une sélection vide, les restarts, les sauvegardes et les surfaces de convection. Le schéma solve–posttraitement–restart–`EKILL` est décrit dans l'[Advanced Analysis Guide 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/pdf/ANSYS_Mechanical_APDL_Advanced_Analysis_Guide.pdf).

Ne pas tuer un élément dès que sa température atteint simplement la température de début de pyrolyse. Cela supprimerait instantanément sa masse et son énergie. La suppression doit intervenir après consommation de l'enthalpie de pyrolyse et lorsque le critère de récession du char est satisfait.

## 7. Pas de temps et résolution du maillage

Choisir le pas de temps afin que le front ne traverse pas une fraction excessive d'une couche pendant un incrément :

$$
\dot s_{max}\Delta t < 0.2\text{ à }0.3\,\Delta r
$$

où $\Delta r$ est l'épaisseur radiale d'un élément ou d'une bande sacrificielle.

Effectuer au minimum :

- un calcul avec le maillage de référence ;
- un calcul avec une taille radiale divisée par deux ;
- un calcul avec un pas de temps divisé par deux.

Les températures de l'aluminium, la profondeur pyrolysée et la masse retirée ne doivent varier que faiblement entre les calculs retenus.

## 8. Calcul de la matière consommée

Pour une approche par éléments désactivés :

$$
m_{retirée}=\sum_{e\,mort}\rho_{ref}V_{e,0}
$$

Utiliser :

- la densité vierge à la température initiale pour la masse initiale ;
- la différence $\rho_{vierge}-\rho_{char}$ pour les gaz de pyrolyse ;
- la densité du char pour le volume de char réellement érodé.

Le bilan total doit séparer la masse transformée en gaz pendant la pyrolyse et la masse solide retirée par la récession de surface.

## 9. Réglages et résultats conseillés

### Réglages d'analyse

- durée : temps de combustion plus une phase de refroidissement ;
- pas de temps automatique avec bornes minimale et maximale ;
- sauvegarde des résultats à chaque sous-pas utile ;
- propriétés dépendantes de la température ;
- contrôles non linéaires activés si radiation, contacts non linéaires ou birth/death sont utilisés.

### Résultats

- `Temperature` sur chaque corps ;
- `Total Heat Flux` ;
- température de surface sur la face chaude courante ;
- température aux interfaces ;
- température maximale de l'époxy ;
- température maximale de l'aluminium ;
- volume et masse des éléments désactivés ;
- profondeur de pyrolyse et profondeur réellement retirée en fonction du temps.

## 10. Vérification physique

Contrôler le bilan d'énergie :

$$
Q_{gaz}\approx Q_{stockée}+Q_{pyrolyse}+Q_{pertes\ extérieures}+Q_{matière\ retirée}
$$

Valider autant que possible avec :

- température extérieure mesurée pendant un tir ;
- thermocouples aux interfaces ;
- épaisseur résiduelle après tir ;
- masse du moteur avant et après tir ;
- essais sur coupons de phénolique avec le même procédé de fabrication.

## 11. Limite de Mechanical

La désactivation produit une frontière en escalier et ne remaille pas réellement la surface. Si le déplacement continu de la paroi doit modifier l'écoulement des gaz et le flux local, utiliser plutôt Fluent avec son modèle transitoire d'ablation et son maillage dynamique : [documentation officielle Fluent](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/flu_ug/flu_ug_sec_wall_ablation.html).

Pour le modèle actuel, la progression recommandée est donc :

1. vérifier la continuité thermique des interfaces ;
2. valider le chargement convection/radiation ;
3. modéliser la pyrolyse à géométrie fixe ;
4. comparer les résultats à des données expérimentales ;
5. seulement ensuite ajouter la désactivation couche par couche.

## 12. Implémentation native de la pyrolyse dans ce projet

La loi précédemment écrite en Python a été remplacée par une routine Fortran
`UserMatTh`. C'est l'interface native de MAPDL pour fournir la conductivité,
la capacité thermique, la densité, le flux, la chaleur de réaction et les
variables d'état à chaque point d'intégration.

Fichiers associés :

- `usermatth.F` : loi d'Arrhenius et mélange vierge/char ;
- `phenolic_pyrolysis_native.apdl` : table `TB,USER`, paramètres cinétiques et
  déclaration des deux variables d'état ;
- `configure_native_usermatth_prebuilt.py` : configuration à exécuter une seule fois
  dans le panneau Scripting de Mechanical ;
- `launch_workbench_native_upf.cmd` : lancement Windows avec les environnements
  Visual Studio et Intel Fortran, construction x64 de `usermatthLib.dll`, puis
  définition de `ANS_USER_PATH` et `ANS_USER_PATH_261`.

### Configuration unique dans Mechanical

1. Fermer Workbench après avoir arrêté le calcul en cours.
2. Relancer le projet avec `launch_workbench_native_upf.cmd`.
3. Dans Mechanical, ouvrir `Automation > Scripting`.
4. Ouvrir puis exécuter `configure_native_usermatth_prebuilt.py`.
5. Enregistrer le projet.
6. Faire le premier essai sur un cœur, tel que configuré par le script.

Le script effectue les changements suivants dans la base Mechanical :

- conserve `PHENOLIC_PYROLYSIS` sur le corps intérieur `phe0` ;
- retire l'ancien `/UPF,usermatth.py` et utilise `usermatthLib.dll` précompilée ;
- supprime le besoin d'un callback Python avant le solve ;
- conserve `OUTRES,SVAR,ALL` pour enregistrer `alpha` et `alpha_dot` ;
- corrige la température initiale de `295.15 °C` à `22 °C`, puisque la valeur
  précédente correspondait manifestement à `295.15 K` saisie avec la mauvaise
  unité ;
- désactive temporairement le solve distribué et fixe le premier essai à un
  cœur.

### Prérequis Windows pour la compilation

La construction `ANSUSERSHARED` d'ANSYS 2026 R1 nécessite les outils de personnalisation
ANSYS, Visual Studio 2022 Professional avec la charge de travail C++ de bureau,
et Intel oneAPI 2023.1 Classic Fortran (`ifort` 2021.9.0). Le lanceur vérifie
ces prérequis avant d'ouvrir Workbench.

Les éditions oneAPI récentes ne contiennent plus `ifort` et leur commande
`setvars` n'initialise que `ifx`. Installer la version 2023.1 côte à côte avec
la version récente à partir de l'[installateur hors ligne indiqué par ANSYS](https://registrationcenter-download.intel.com/akdlm/IRC_NAS/2a13d966-fcc5-4a66-9fcc-50603820e0c9/w_HPCKit_p_2023.1.0.46357_offline.exe).
Le lanceur sélectionne explicitement le dossier `compiler\2023.1*` afin que la
présence d'une édition oneAPI plus récente ne masque pas `ifort`.

Sur Windows 11 ARM64 sous Parallels, le script `ANSUSERSHARED.bat` d'ANSYS ne
reconnaît pas `PROCESSOR_ARCHITECTURE=ARM64`. Le projet utilise donc
`build_usermatth_x64.cmd`, qui reproduit les options officielles en imposant la
cible x64 émulée et vérifie l'export `USERMATTH` dans la DLL.
Ce forçage ne doit jamais être propagé à Workbench ou à `ANSYS261.exe` : le
lanceur conserve l'environnement ARM64 normal afin que Windows gère lui-même
la couche d'émulation x64.

### Vérification dans la sortie du solveur

La sortie ne doit plus contenir le message de l'ancien service Python. Chercher
plutôt :

```text
Prebuilt Fortran UserMatTh pyrolysis model requested
NOTE: This Mechanical APDL version was linked by Licensee
```

Vérifier ensuite que `SVAR1` évolue de 0 vers 1 dans `phe0`. Une valeur
strictement supérieure à zéro sur la face chaude démontre que la routine est
appelée. `SVAR2` est la vitesse instantanée de conversion en `s^-1`.

Après ce premier test réussi, garder `Distribute Solution = No` et augmenter
progressivement le nombre de cœurs SMP jusqu'à 14. La routine Fortran
n'utilise aucune variable globale modifiable et est donc sûre vis-à-vis des
threads. Le DMP Windows demande en plus un chemin `ANS_USER_PATH` UNC vers le
nœud principal ; il est inutile pour ce calcul sur une seule machine et n'est
pas activé par cette configuration.
