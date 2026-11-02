# Desk API and evidence contracts

All `/api/cases`, `/api/records` and `/atlas` routes require an authenticated HttpOnly session. The browser shell, static assets, `/healthz` and the boolean `/api/session` status contain no analyst records. Sign in with `POST /api/session` (`access_key`), then sign out with `DELETE /api/session`. Mutations require `X-Desk-Request: 1`; no cross-origin API access is enabled.

| Operation | Contract |
| --- | --- |
| `GET /api/cases` | `{items: [{id,title,created_at}]}` |
| `POST /api/cases` | `{title}`, returns created case, HTTP 201 |
| `GET /api/cases/{id}/records?q=&kind=&offset=0&limit=50` | Literal search across title/body/payload; maximum query 200 characters, page size 100; `{items,total,offset,limit}` |
| `POST /api/cases/{id}/records` | Full `RecordWrite`, returns created record, HTTP 201 |
| `GET /api/records/{id}` | Full record, revision and typed backlinks |
| `PUT /api/records/{id}` | Full `RecordWrite` plus expected `revision`; mismatch returns 409 without overwriting |
| `GET /api/records/{id}/history` | `{items:[...]}` complete saved snapshots, newest first |
| `GET /api/cases/{id}/graph` | Record nodes and explicit typed edges; not inferred political relations |
| `GET /api/cases/{id}/export` | JSON case, records, relationships and revisions; no sessions |

Write fields: `kind`, `title`, `body`, `url`, `source_id`, `document_id`, `excerpt`, `locator`, `published_on`, `reviewed_on`, `event_on`, `confidence`, `confidence_reason`, `tags`, `links`. Unknown fields are rejected. Record kinds are `source`, `document`, `claim`, `note`, `actor`, `event`, `theme`. Types cannot change after creation. Notes can hold alternative hypotheses, gaps and assessments; actor/event labels are analyst-authored records, not independently verified entities or event geolocation.

Sources require a public HTTP(S) URL. A document requires a publisher source in the same case. A claim requires a document in the same case, an **exact excerpt occurring in its stored text**, and a page/paragraph locator. Traceability is not truth: an excerpt match does not establish that it supports the interpretation, is authentic or independently corroborated. Confidence (`unassessed`, `low`, `medium`, `high`) is a human judgment; assessed confidence requires a written rationale. It is never an automatic publisher reliability score. Dates are independent ISO days and may be null.

Links must target existing records in the same case. Explicit links produce `references` edges, documents produce `published_by`, and claims produce `cites_excerpt_from`. Edits that remove an excerpt cited by a claim are rejected. Source/document/content changes remain visible in revision history, but this is not a signed or tamper-proof audit system. A database administrator can change the database directly.

Errors use `{error:{code,message}}`: 401 sign-in required, 403 request boundary, 404 unknown record/case, 409 revision or citation conflict, 413 oversized request, 422 invalid fields/references, 429 sign-in throttle and 503 storage unavailable. Error bodies do not reflect raw input payloads. A failed write keeps the browser draft. If a network failure makes the result uncertain, reload the library before repeating a **create** operation; create requests do not yet have client idempotency keys. Updates use revisions to prevent duplicate overwrites.

Claims also return a server-produced `citation_provenance` snapshot with the cited document revision, URL, publisher reference, excerpt/locator and distinct publication/review dates. Clients cannot supply this snapshot in ordinary writes. A later document revision does not silently change the earlier claim's saved citation snapshot.

JSON case export is bounded to 10,000 records; use a consistent operator database backup for larger datasets and disaster recovery. The browser reference selector loads at most 1,000 records per case and warns at that boundary; the API and full export retain all records. Search pages are 50 records. There is no destructive delete or arbitrary JSON/file upload endpoint in this version. There is no generic URL fetch endpoint. No private data or real service credentials belong in repository fixtures.

The administrator-only offline `restore-case --input FILE` command validates a version-1 JSON export and restores a new case in one transaction. It rejects conflicting case/record IDs, dangling relationships, invalid URL schemes, missing histories and claim snapshots without their cited document revision. It is not a web upload or an overwrite/import-merge endpoint.
