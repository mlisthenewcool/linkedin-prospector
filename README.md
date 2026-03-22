# Automatisation Prospection LinkedIn

Outil CLI d'automatisation de prospection LinkedIn via Playwright. Import de prospects depuis CSV, envoi d'invitations, messages personnalisés et relances avec simulation de comportement humain.

## Pipeline

```
CSV → import → [new] → connect → [connection_sent] → sync → [connected] → message → [messaged] → followup → [followed_up]
                                                                                          ↓
                                                                                      [replied] → sort du pipeline
```

## Installation

```bash
uv sync
uv run playwright install chromium
```

## Configuration (obligatoire)

Modifier `config.toml` :

```toml
[user]
# OBLIGATOIRE — doit correspondre exactement au nom affiché sur LinkedIn
first_name = "Prénom"
last_name = "Nom"
title = "Votre titre"
```

Les templates de messages dans `message_templates/` sont aussi obligatoires :
- `connection_note.txt.j2` — note d'invitation (max 300 chars)
- `first_message.txt.j2` — premier message de prospection
- `follow_up.txt.j2` — message de relance

## Configuration (facultative)

Dans `config.toml`, les valeurs par défaut conviennent pour la plupart des cas :

| Section | Paramètre | Défaut | Description |
|---------|-----------|--------|-------------|
| `limits` | `invitations_per_day` | 30 | Limite quotidienne d'invitations |
| `limits` | `messages_per_day` | 30 | Limite quotidienne de messages |
| `limits` | `followups_per_day` | 30 | Limite quotidienne de relances |
| `delays` | `min_delay` / `max_delay` | 30-120s | Délai aléatoire entre chaque action |
| `delays` | `followup_after_days` | 5 | Jours avant relance |
| `browser` | `headless` | false | Mode sans fenêtre |
| `paths` | `database` | `data/prospector.db` | Chemin de la base SQLite |
| `--config` | — | `config.toml` | Chemin alternatif via CLI |

## Commandes

### Obligatoires au premier lancement

```bash
# 1. Se connecter à LinkedIn (ouvre un navigateur, login manuel)
uv run python -m src.main login

# 2. Importer des prospects depuis un CSV (colonnes : linkedin_url + optionnelles)
uv run python -m src.main import --csv prospects.csv
```

### Commandes principales

```bash
# Synchroniser les statuts avec l'état réel LinkedIn (déjà connecté ? message envoyé ? réponse ?)
uv run python -m src.main sync --limit 10

# Envoyer des invitations aux prospects "new"
uv run python -m src.main connect --limit 5

# Envoyer le premier message aux prospects "connected"
uv run python -m src.main message --limit 5

# Relancer les prospects "messaged" sans réponse
uv run python -m src.main followup --limit 5
```

### Consultation

```bash
# Statistiques par statut + compteurs du jour
uv run python -m src.main status

# Lister les prospects (filtrage optionnel)
uv run python -m src.main list --limit 20
uv run python -m src.main list --status connected
```

## Format CSV

Colonne obligatoire : `linkedin_url` (ou alias : `url`, `profile_url`, `linkedin`, `profile`)

Colonnes optionnelles : `first_name`, `last_name`, `headline`, `company`
