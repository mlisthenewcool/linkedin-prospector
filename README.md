# LinkedIn Prospection Automation

CLI tool for LinkedIn prospection automation via Playwright. Import prospects from CSV, send connection requests, personalized messages and follow-ups with human behavior simulation.

## Pipeline

```
CSV → import → [new] → connect → [connection_sent] → sync → [connected] → message → [messaged] → followup → [followed_up]
                                                                                          ↓
                                                                                      [replied] → exits pipeline

Navigation errors → [invalid_profile] → excluded from future actions
```

## Installation

```bash
uv sync
uv run playwright install chromium
```

## Configuration

Edit `config/config.toml`:

```toml
[limits]
invitations_per_day = 30
messages_per_day = 30
followups_per_day = 30
actions_per_session = 40

[delays]
min_delay = 30       # seconds between actions
max_delay = 120
followup_after_days = 5

[browser]
headless = false
slow_mo = 50         # ms between each Playwright action

# [user]
# Optional — auto-detected from LinkedIn at login.
# Uncomment to override:
# first_name = "FirstName"
# last_name = "LastName"
# title = "My title"
```

Message templates in `config/templates/`:
- `first_message.txt.j2` — first prospection message (Jinja2)
- `follow_up.txt.j2` — follow-up message

## Commands

### First-time setup

```bash
# 1. Log into LinkedIn (opens a browser, manual login)
prospect login

# 2. Import prospects from a CSV
prospect import --csv data/prospects_example.csv
```

### Main commands

```bash
# Sync statuses with actual LinkedIn state (connected? message sent? reply?)
prospect sync --limit 10

# Send connection requests to "new" prospects
prospect connect --limit 5

# Send first message to "connected" prospects
prospect message --limit 5

# Follow up with "messaged" prospects who haven't replied
prospect followup --limit 5
```

### Viewing data

```bash
# Statistics by status + daily counters
prospect status

# List prospects (optional filtering)
prospect list --limit 20
prospect list --status connected

# Export prospects to CSV
prospect export --output export.csv
prospect export --status replied --output replied.csv
```

## CSV format

Required column: `linkedin_url` (aliases: `url`, `profile_url`, `linkedin`, `profile`)

Optional columns: `first_name`, `last_name`, `headline`, `company`

An example file is available at `data/prospects_example.csv`.

## Project structure

```
config/
  config.toml              # Main configuration
  linkedin_user.toml       # Auto-detected LinkedIn user (gitignored)
  templates/               # Jinja2 message templates
    first_message.txt.j2
    follow_up.txt.j2
data/                      # Runtime data (gitignored except example)
  prospects_example.csv    # Example CSV with fake data
  prospector.db            # SQLite database (auto-created)
  session/state.json       # Browser session (auto-created)
logs/                      # Log files (gitignored)
src/
  main.py                  # CLI entrypoint (typer)
  config.py                # TOML config loader + path constants
  database.py              # SQLite schema and CRUD
  models.py                # Prospect, Action dataclasses
  csv_importer.py          # CSV import logic
  browser.py               # Playwright + stealth browser manager
  templates.py             # Jinja2 template engine
  workflow.py              # Pipeline orchestration
  linkedin/
    auth.py                # Login, session validation
    navigator.py           # Profile navigation with human simulation
    profile_parser.py      # Profile info extraction
    connection.py          # Connection request sending
    conversation.py        # Messaging: open, scan, send
    messenger.py           # First message + follow-up logic
    sync.py                # Status synchronization
  safety/
    human_behavior.py      # Delays, typing, scrolling, mouse, noise
    rate_limiter.py        # Daily + session rate limiting
```
