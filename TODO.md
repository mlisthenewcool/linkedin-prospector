<!-- ===== Formatting conventions =====
 - Sections       : Now / Next / Later / Done
 - Open format    : - [ ] [Domain] Description (imperative form)
 - Done format    : - [x] [Domain] _(YYYY-MM-DD)_ Description
 - Open sorting   : alphabetical by domain, then by description
 - Done sorting   : descending date (most recent first)
 ===== -->

# TODO

## Now

- [ ] [Config] Lower the default limits
- [ ] [Tooling] Compare prek.toml with the other project's version

## Next

- [ ] [CSV] Verify that import works without a company name
- [ ] [CLI] Add recruiter search by company name (parameter)

## Later

- [ ] [Prospection] Implement "cold" prospection (generic message, no job offer found)
- [ ] [Prospection] Implement "targeted" prospection (company CSV + job URL, recruiter tagging, custom message)

## Done

- [x] [Config] _(2026-03-23)_ Remove [paths] section, hardcode as constants
- [x] [Code] _(2026-03-23)_ Remove dead code (close_message_dialog, unused params)
- [x] [Git] _(2026-03-23)_ Purge sensitive prospect data from git history
- [x] [Project] _(2026-03-23)_ Restructure project layout (config/, data/)
- [x] [Git] _(2026-03-22)_ Expand .gitignore
- [x] [Logs] _(2026-03-22)_ Migrate logging to structlog
- [x] [Models] _(2026-03-22)_ Adopt None instead of empty strings for nullable values
- [x] [Models] _(2026-03-22)_ Add require_id() and display_name on Prospect
- [x] [Models] _(2026-03-22)_ Switch dataclasses to frozen=True, slots=True
- [x] [Models] _(2026-03-22)_ Analyze removing None after sync (conclusion: about/company/headline legitimately None)
- [x] [Project] _(2026-03-22)_ Group config, templates and linkedin_user.toml into config/
- [x] [Project] _(2026-03-22)_ Move import CSVs to examples/
