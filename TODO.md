1) config
- limits : commencer plus bas
- est-ce qu'on ne devrait pas déplacer dans src/

2) .gitignore plus complet

3) prospects.csv & prospects_pylote.csv -> data

4) logs : ajouter structlog + améliorer les messages

5) prek : comparer avec celui de l'autre projet

[done, mais à modifier] 6) mets à jour tous les models
- si une valeur peut-être nulle, utilise None, pas une chaine de caractères vide
- idéalement, utilise des dataclass frozen+slot=True si c'est mieux et pertinent pour l'usage, sinon, pydantic a t il une valeur ajoutée supplémentaire ? normalement si les données ne sont pas des input utilisateur, dataclass suffit vs pydantic non ?
[todo] pourquoi ne pas retirer la possibilité du None ? au départ OK on a pas toutes les infos, mais après un sync on doit toutes les avoir. ce n'est qu'à l'import que c'est toléré

7) actuellement, fonctionne avec un fichier .csv importé qui a le lien linkedin du profil + un nom d'entreprise.
- est-ce que ça fonctionnerait sans le nom d'entreprise ?
- est-ce qu'il serait possible de chercher des recruteurs qui travaillent pour une entreprise dont on fournirait le nom comme paramètre ?

8) idéalement j'aimerais avoir deux types de prospection :
- une prospection "froide" à qui on envoie un type de message générique car on a pas trouvé d'offres d'emploi de l'entreprise pour laquelle travaille le prospect
- une prospection "ciblée" : je vais remplir dans un csv le nom de l'entreprise ainsi que l'url d'une offre de mission / d'emploi que j'ai vu et qui correspond à mes attentes/compétences ; il faudrait pouvoir fournir ce csv qui permette d'ajouter les recruteurs de cette entreprise et de les tagger spécifiquement pour être ensuite en mesure de leurs envoyer un message plus ciblé, qui comprenne l'offre d'emploi vue
