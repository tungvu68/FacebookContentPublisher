# Facebook Content Publisher

Windows desktop application for preparing localized Facebook Page content. Milestones
1–3 provide the PySide6 shell, domain/SQLite foundation, Country management, Campaign
drafts, multi-country targets, and media selection. OpenAI and Facebook remain in clearly
labelled **mock mode**; no key, token, or other secret is required.

## Setup

Requirements are Windows 10/11 and PowerShell 5.1+. The first setup needs Internet access.
No global Python installation is required: everything is placed in `.tools` and `.venv`
inside this project.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

The setup script is idempotent.

## Database

The app automatically upgrades the database and inserts missing development countries on
startup. Manual commands are also available:

```powershell
.\.venv\Scripts\python.exe -m facebook_content_publisher.infrastructure.database.cli initialize
.\.venv\Scripts\python.exe -m facebook_content_publisher.infrastructure.database.cli upgrade
.\.venv\Scripts\python.exe -m facebook_content_publisher.infrastructure.database.cli seed
```

SQLite normally lives under the platform application-data directory at
`FacebookContentPublisher\data\app.db`. Set `FCP_DATA_DIR` or pass
`--database C:\path\to\app.db` for an isolated development database. Alembic revision
`0002` adds `campaign_targets`, including the unique Campaign/Country constraint.

The development seed contains Thailand, Indonesia, and Brazil and is idempotent.

## Run

```powershell
.\scripts\run.ps1
```

The Countries page supports search, enabled filtering, create/edit, enable/disable, and
confirmed deletion. New Campaign supports multi-country targets, per-country link override,
immediate/scheduled mode, delayed-comment settings, and drag/drop or browsed media. The
Campaigns page supports search, status filter, edit/view, duplicate, archive, and safe Draft
deletion. Selected source files are referenced only; the application never modifies or
deletes original media.

`Generate Translations` validates and saves the draft, then explicitly reports that the
translation engine belongs to Milestone 4—it makes no OpenAI request.

## Test and build

```powershell
.\scripts\test.ps1
.\scripts\build.ps1
```

Tests run Ruff format/lint, offline unit and integration tests, migrations, and an offscreen
Qt smoke test. Build repeats those checks before PyInstaller creates
`dist\FacebookContentPublisher\FacebookContentPublisher.exe`.

## Architecture and security

```text
UI → Application DTOs/services → Domain models/interfaces ← Infrastructure adapters
```

UI widgets never own database sessions. Campaign aggregate writes are transactional.
Media SHA-256 uses chunked reads, and the UI validates selected files on a thread-pool
worker. `.env`, databases, caches, environments, logs, and builds are ignored by Git.
`.env.example` contains modes only and no credentials.

Production OpenAI/Facebook adapters, translation review, credential storage, scheduling,
publishing, and background jobs are deliberately outside Milestone 3.

## Dynamic translation prompt

Translation preparation uses one versioned English base prompt shared by every country.
`CountryProfile` supplies the country, language, locale, native-reader label, localization
level, comment template, link, hashtags, and an optional short override. The source text is
always placed last; the JSON schema is supplied separately by a provider adapter and is not
duplicated in the prompt.

To add a language, create a CountryProfile in the Countries screen—do not add a hard-coded
country prompt. Set a clear native-reader label and choose `conservative`, `natural`, or
`strong`. An override should contain only a genuine country-specific nuance; attempts to
change the output language, ignore base rules, expose secrets, invent, omit, or summarize
content are rejected.

Structured translation results carry input, output, and cached-input token counts when a
provider supplies them. The database fields `input_tokens`, `output_tokens`, and
`cached_input_tokens` prepare usage display/reporting for the full Milestone 4 workflow.
Credential-like values are redacted from rendered dynamic prompt content.

## Next milestone

Milestone 4 will add the translation service interface, offline mock translator, official
OpenAI Responses API adapter, structured-output validation, review/edit/approval UI,
secret storage, and translation tests.
