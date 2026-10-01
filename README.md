# Facebook Content Publisher

## Milestone 5 — persistent mock scheduler

Approved translations can now be converted into immediate or scheduled publication jobs.
SQLite is the source of truth; the background worker uses transactional claims, expiring
leases, persisted exponential retry times and idempotency keys. Successful mock publications
create at most one delayed comment job, calculated from the actual publish timestamp.

The Scheduled Jobs page supports search, status filters, run/retry/cancel and guarded manual
completion for ambiguous results. `UNKNOWN_RESULT` is never retried automatically. The tray
menu can open the app, pause/resume the scheduler, wake due jobs, or exit. All Facebook IDs and
URLs are visibly fake and no Facebook credential or network request is used.

Start the app with `scripts\run.ps1`; run all offline checks with `scripts\test.ps1`; build the
Windows onedir package with `scripts\build.ps1`.

## Milestone 6 — desktop and scheduler hardening

- Publication and comment execution use separate bounded worker pools. Transactional claims,
  owner-scoped leases, periodic heartbeats and a scan lock prevent duplicate execution.
- Job Details shows detached snapshots and activity history. Safe diagnostics exclude post,
  comment, media and raw metadata content. Reschedule uses optimistic versions and rejects races.
- Scheduler settings validate concurrency, polling, lease/heartbeat, shutdown, retry, overdue,
  notification and tray options. Worker-count changes apply after application restart.
- Start with Windows uses the current-user Windows Run key only in a packaged build, is off by
  default, and never requests administrator rights. Turning it off removes only the
  `FacebookContentPublisher` value; uninstallers should call the same disable operation.
- Jobs older than the configured grace period are held for operator attention when confirmation
  is enabled. They can then be run, rescheduled or cancelled from Scheduled Jobs.
- Facebook provider selection fails closed in `graph_api` mode with
  `Facebook production connection is not configured`. Milestone 6 never contacts Meta.
- The Dashboard, Scheduled Jobs and Logs views use SQLite-backed metrics and audit events.

Milestone 7 will need the Meta application configuration, Page authorization workflow and real
Graph API adapter. Do not place tokens or App Secrets in repository files.

## Milestone 7A — offline Facebook production integration

The project now contains a typed, injectable Graph HTTP client; structured error mapping;
keyring-backed per-Page credential aliases; an OAuth broker boundary; Page connection metadata;
and `GraphApiFacebookPublisher` adapters for text, photo, video and comments. All default tests use
`httpx.MockTransport`, and production publishing is disabled by default.

Mock and production jobs are selected by their immutable `provider_mode_snapshot`. Missing Page
credentials, a disabled production safety switch, or absent broker configuration fail closed and
never fall back to the mock publisher. The Facebook Pages screen offers an offline mock connection;
live Connect remains disabled until Phase 7B configuration is verified.

See `docs/META_SETUP.md`, `docs/META_OAUTH_THREAT_MODEL.md`, and
`docs/META_APP_REVIEW.md`. The official Meta pages were unreachable from the documentation-check
environment on 2026-10-01, so `v24.0`, candidate permissions, endpoints, and especially the video
upload flow must be re-verified against current Meta documentation before any live test.

Windows desktop application for preparing localized Facebook Page content. Milestones
1–4 include Country/Campaign management, concurrent structured translation, OpenAI
Responses API support, secure credential storage, and translation review. The safe default
is **mock mode**, which needs no key, token, or network access.

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
`0004` is the current head and adds translation lifecycle, recovery, source-hash, request ID,
failure and manual-review metadata. Earlier revisions remain unchanged.

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

`Generate Translations` validates and saves the draft, translates targets concurrently,
persists each result immediately, and opens Translation Review. Review supports editing,
approval, rejection, retry and regeneration. Mock mode remains fully offline.

## Configure OpenAI

Open **Settings → OpenAI**, select `openai`, choose a model, timeout, concurrency and retry
limits, then enter the API key with **Set / Replace Key**. The key is saved only through
Windows Credential Manager under `FacebookContentPublisher/v1`; it is never written to
SQLite, settings JSON, logs, source, or repopulated into the key field. Use **Test
Connection** to make a minimal structured Responses API request. Switching modes never
initiates a request.

The adapter uses `client.responses.parse(...)` with the strict Pydantic
`TranslationOutput`, disables response storage, tools, streaming and conversation history,
and validates the locale again after parsing. Provider tests use fake SDK clients; no live
test runs by default.

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

Facebook production, publishing, comments, scheduling and background jobs remain outside
Milestone 4.

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
`cached_input_tokens` are displayed in Translation Review when supplied by the provider.
Credential-like values are redacted from rendered dynamic prompt content.

## Packaging

`build\` is an intermediate PyInstaller directory and must not be executed. The supported
packaged application is only:

```text
dist\FacebookContentPublisher\FacebookContentPublisher.exe
```

## Next milestone

Milestone 5 will add persistent publication/comment scheduling, retry/recovery workers,
system tray integration and background-job status. It will not change credential handling.
