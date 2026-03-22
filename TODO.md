<!-- ===== Conventions de formatage =====
 - Sections       : Maintenant / Ensuite / Plus tard / Terminé
 - Format ouvert  : - [ ] [Domaine] Description (forme impérative)
 - Format terminé : - [x] [Domaine] _(YYYY-MM-DD)_ Description
 - Tri ouvert     : alphabétique par domaine, puis par description
 - Tri terminé    : date décroissante (plus récent en premier)
 ===== -->

# TODO

## Maintenant

- [ ] [Config] Baisser les limits par défaut
- [ ] [Tooling] Comparer prek.toml avec celui de l'autre projet

## Ensuite

- [ ] [CSV] Vérifier que l'import fonctionne sans nom d'entreprise
- [ ] [CLI] Ajouter la recherche de recruteurs par nom d'entreprise (paramètre)

## Plus tard

- [ ] [Prospection] Implémenter la prospection "froide" (message générique, pas d'offre trouvée)
- [ ] [Prospection] Implémenter la prospection "ciblée" (CSV entreprise + URL offre, tagging recruteurs, message personnalisé)

## Terminé

- [x] [Models] _(2026-03-22)_ Adopter None au lieu de chaînes vides pour les valeurs nullables
- [x] [Models] _(2026-03-22)_ Ajouter require_id() et display_name sur Prospect
- [x] [Models] _(2026-03-22)_ Passer les dataclass en frozen=True, slots=True
- [x] [Models] _(2026-03-22)_ Analyser le retrait de None après sync (conclusion : about/company/headline légitimement None)
- [x] [Logs] _(2026-03-22)_ Migrer logging vers structlog
- [x] [Projet] _(2026-03-22)_ Regrouper config, templates et linkedin_user.toml dans config/
- [x] [Projet] _(2026-03-22)_ Déplacer les CSV d'import dans examples/
- [x] [Git] _(2026-03-22)_ Compléter le .gitignore
