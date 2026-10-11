# Récupération autorisée d'un faux rejet POST1 après `EKILL`

L'utilisateur autorise, pour les exécutions futures de `newmotor_phenolic_study/v0`, la répétition de la manœuvre de récupération décrite ici lorsque **la même signature exacte** réapparaît. Cette autorisation ne vaut pas pour un autre type d'arrêt.

## Signature obligatoire

Toutes les conditions suivantes doivent être démontrées avant toute écriture ou reprise :

- le pas MAPDL s'est terminé et a convergé normalement ;
- le contrôleur a échoué uniquement avec `Missing, duplicate or resurrected solid fields` ;
- les exports élémentaires et énergétiques contiennent les mêmes identifiants, sans doublons ;
- tous les éléments vivants attendus sont présents ;
- aucun identifiant étranger au maillage n'est présent ;
- les seuls identifiants excédentaires correspondent exactement à des éléments de rangées déjà déclarées mortes dans l'état accepté ;
- le temps observé correspond à la cible en attente ;
- les bilans de convection et d'énergie restent sous les seuils inchangés ;
- les dix partitions du restart courant sont présentes, non vides et temporellement cohérentes ;
- le runtime arrêté a été préservé séparément avant la réparation.

Le phénomène connu vient de MAPDL 2026 R1.02 : POST1 peut encore exporter les lignes de `SOLID278` déjà tués, malgré la sélection `LIVE`. Ces lignes périmées ne doivent pas entrer dans l'état physique accepté.

## Manœuvre autorisée

1. Préserver le runtime échoué dans un dossier frère horodaté, avec les preuves et journaux originaux.
2. Travailler dans une copie distincte.
3. Utiliser le contrôleur corrigé, qui filtre uniquement les identifiants excédentaires déjà déclarés morts et conserve toutes les vérifications strictes sur les éléments vivants.
4. Exécuter `v0/model/recover_postkill_export.py` avec `--root`, `--evidence` et l'option explicite `--apply`.
5. Vérifier l'acceptation du pas, les deux bilans, l'état `PAUSED_AT_CHECKPOINT`, la provenance SHA-256 et le nouveau manifeste.
6. Exécuter le préflight natif sans `SOLVE`.
7. Reprendre explicitement avec 10 rangs, puis vérifier que le premier pas suivant est accepté avant de considérer la récupération réussie.

## Refus obligatoire

Ne pas appliquer cette manœuvre en cas de champ vivant absent, doublon, identifiant étranger, divergence MAPDL, erreur de bilan, incohérence de restart, erreur différente, ou doute sur la correspondance index/temps. Ne jamais baisser un seuil, fabriquer ou renommer une génération de restart, ni relancer à zéro sous couvert de cette autorisation.

La récupération doit toujours laisser une archive intacte, un `RECOVERY_PROVENANCE.json`, l'erreur originale conservée et des empreintes des dix partitions utilisées.
