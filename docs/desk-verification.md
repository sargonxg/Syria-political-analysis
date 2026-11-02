# Private desk verification

This checkpoint reconciles upstream main `3617dda3095a4e647754243901d836d06f080d2f` with the source-atlas branch. Existing country workspaces, eight analytical layers and the qualified political ontology are retained alongside 39 source profiles and 17 documented atlas relationships. The current public corpus has 44 document references, 14 attributed paraphrases and 14 regional anchors. Source evidence, catalogue provenance and five verified endpoint registrations were preserved; no collection was run to manufacture fresh coverage.

## Local checks

- 51 Python tests passed on Windows/Python 3.12, covering the original toolkit, country isolation, political ontology, catalogue and desk.
- Ten desk tests cover exact excerpt/locator requirements, written confidence rationale, pinned citation revisions, guarded document edits, optimistic conflicts, repeated revisions, SQLite reopening, literal Unicode search, case-local references, backups, newer-schema refusal, idempotent public import, authenticated APIs, cookie/CSRF boundaries, invalid inputs, request limits, throttling and transactional case restoration.
- 23 real-browser checks passed with synthetic records only: empty state, source/document/claim/note/actor/event/theme creation, invalid-citation draft preservation, repeated edits/history, stale-tab 409 feedback, search empty results, backlinks, keyboard graph activation/focus, case export, persisted reload, sign-out/direct API rejection, light/dark mode, no page overflow at 320/768/1440 pixels and no uncaught JavaScript errors. Expected HTTP 422/409 responses during deliberate error tests are not reported as uncaught errors.
- Browser export contained seven synthetic records, three explicit relationships and ten revision snapshots. Offline tests round-trip a case into a clean database retaining IDs/backlinks/history; invalid input leaves no partial case.
- Scoped Ruff lint/format, JavaScript syntax and Prettier checks passed. The existing ontology test gained an explicit UTF-8 read for Windows.
- Runtime dependency audit of `requirements-desk.lock` reported no known vulnerabilities at the check time. This is not a guarantee against undisclosed vulnerabilities. Package versions are pinned; package hashes are not.
- Python wheel build is checked separately from container execution. Docker is unavailable on the laptop, so no local container build or cloud deployment is claimed. The PR's tests-only CI builds the image and runs a disposable loopback health/authentication smoke test.

The first restricted Windows asyncio test run stalled while opening its loopback socket pair; the same tests completed outside that process sandbox. An open SQLite backup handle found by the Windows cleanup test was fixed. Early browser fixture timing/session issues were corrected with explicit loaded-state waits and isolated synthetic-session reset.

## Design and security gate

Hard gate PASS: the desk starts empty, uses real saved data, validates citations and errors visibly, preserves failed drafts, and exercises every application control in tests. Purpose gate PASS: the paper/green editorial design follows the existing atlas; typed nodes and labelled explicit links convey structure without fabricated influence scores. Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; a source library, authoring pane and local graph serve actual research tasks. Craftsmanship PASS: both themes and mobile layouts were inspected; data is inserted as text rather than HTML, dates and confidence remain explicit, and version conflicts prevent silent stale overwrites.

The application is a single shared-operator workspace, not a multi-tenant security product. No AI provider, arbitrary URL fetcher, PDF/Office parser, public-default deployment or real service key is supplied. Databases and backups are private, untracked application data. Shared access, plaintext-at-application-layer storage, lack of per-user attribution and administrator-editable history are documented limits. Case exports include notes and history, so must be protected.

## GitHub and deployment boundary

Workflows were inspected before pushing: only tests/build and manual public-reference collection are present. No deployment workflow, image publishing, infrastructure provisioning, cloud credentials or account/security changes are introduced. The draft PR is for review; it is not merged. Inspect the PR checks for the exact head SHA for container/Linux/Windows/browser results; local results alone are not a remote CI result.

Read [deployment instructions](deployment.md), [API contracts](desk-api.md) and [analysis method](analysis-method.md). No cloud deployment was performed. Container execution, a production proxy, real access controls, encrypted storage and off-host restore drills must be verified by an operator before operational use.

Self-evaluation: accuracy 4/5 (traceability and tests are explicit, source truth remains a human judgment); completeness 4/5 (working private notebook and container path, with no optional AI or multi-user service); clarity 4/5 (contracts and limits documented); actionability 4/5 (local run, backup/restore and cloud instructions); conciseness 4/5 (reuses Python/SQLite and the existing atlas without a separate frontend framework). Overall 4.0/5. Highest-impact follow-ups are external authentication review, operational backup drills and a PostgreSQL/per-user design only if real usage requires concurrency.
