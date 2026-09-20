# Simulation 2 — secteur 0,10°

Ce dossier est une variante autonome du modèle Simulation 2. Le projet source
`tmp3_sim2` n'a pas été modifié.

## Fichiers à utiliser

- Projet Workbench directement ouvrable :
  `workbench_project/sector_0p10deg.wbpj`
- Archive Workbench autonome :
  `simulation2_sector_0p10deg_selfcontained.wbpz`
- Géométrie neutre : `simulation2_sector_0p10deg.step`
- Géométrie OpenCASCADE : `simulation2_sector_0p10deg.brep`
- Contrôle des dimensions : `geometry_validation.json`
- Contrôle du maillage : `mesh_validation.txt`

La géométrie importée par Workbench est stockée dans le projet sous
`sector_0p10deg_files/import_files`. La DLL, sa source Fortran, les fichiers
APDL et les scripts de reproduction sont copiés sous
`sector_0p10deg_files/user_files`. Le projet peut donc être déplacé avec son
dossier `_files` sans dépendre du modèle source.

## Géométrie

- Angle du secteur : 0,10°
- Facteur de remise à l'échelle vers l'anneau complet : 3600
- Axe du cylindre : Y global
- Longueur axiale conservée : 50 mm, de Y = 914,4 à 964,4 mm
- Phénolique intérieur : R = 66,675 à 67,945 mm, épaisseur 1,270 mm
- Époxy : R = 67,945 à 68,2625 mm, épaisseur 0,3175 mm
- Phénolique extérieur : R = 68,2625 à 71,4375 mm, épaisseur 3,175 mm
- Aluminium : R = 71,4375 à 76,200 mm, épaisseur 4,7625 mm

Ces valeurs utilisent les diamètres nominaux corrigés de 133,350 à
152,400 mm ; elles ne reproduisent pas l'erreur historique qui traitait les
diamètres comme des rayons.

## Maillage généré dans Mechanical

- Type : hexaèdres linéaires à 8 nœuds (`kHex8`)
- Total : 35 200 éléments et 54 540 nœuds
- Direction angulaire : 2 éléments sur 0,10°
- Direction axiale : 100 éléments sur 50 mm
- Phénolique intérieur : 64 couches radiales, 12 800 éléments
- Époxy : 16 couches radiales, 3 200 éléments
- Phénolique extérieur : 64 couches radiales, 12 800 éléments
- Aluminium : 32 couches radiales, 6 400 éléments

La résolution radiale nominale du phénolique intérieur est de
1,270 / 64 = 0,01984 mm, adaptée à un essai de suppression progressive
d'éléments.

## État du modèle

La géométrie, les affectations de matériaux et le maillage sont enregistrés et
validés. Le modèle n'est pas encore déclaré prêt à résoudre : avant un calcul,
il faut reconstruire et contrôler les portées des contacts et des conditions
thermiques sur la nouvelle topologie, ajouter les conditions de symétrie
adiabatique sur les deux plans angulaires, puis adapter le contrôleur
d'ablation au maillage sectoriel.

