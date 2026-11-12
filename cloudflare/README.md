# Read-only research database

The historical atlas can query a real SQLite database locally or a D1 binding in
a Cloudflare Worker. Static snapshots remain usable on their own. Database mode
returns a bounded page of matching records; it does not claim the map contains
every matching observation. A failed database request never supplies replacement
static rows without an explicit change of mode.

## Build locally

From the repository root, with the package installed in your Python environment:

```sh
python scripts/build_research_database.py --output output/research-db
```

The destination must be new. The builder verifies the committed GED snapshot,
all original provider-row digests, the country connector's saved files/licences,
source-profile evidence, and semantic-lens definitions. It performs no network
requests. It writes:

| File | Purpose |
| --- | --- |
| `research.sqlite3` | Local database, usable by standard SQLite clients |
| `research.sql` | D1-compatible import into a new empty database |
| `build-receipt.json` | Source manifest identities, counts, output hashes and import bounds |
| `query-bounds-upgrade.sql` | Separately reviewed metadata patch for the exact same already-imported snapshot; never applied by the builder |

The November 2026 snapshot contains 120,576 retained GED events from provider
years 2000–2025, 15,272 separate annual country values, 55 attributed source
profiles, and five semantic lenses. All 49 original event fields remain in JSON.
Whole source manifests are stored as ordered UTF-8 chunks, allowing exact
reconstruction and SHA-256 verification. No generated ownership/affiliation
links, bias scores, live news claims, forecasts, or model answers are inserted.

Every generated SQL statement is under 95,000 bytes, below D1's documented
100,000-byte statement limit. Parent manifests precede their chunks; indexes
and all data precede readiness metadata. The last `state="ready"` marker is
required before the API reports availability. There are no destructive `DROP`
statements or remote `BEGIN`/`COMMIT` wrappers. Existing output is refused.

Keep import files byte-preserving. For a programmatic SQLite replay, use
`Path("research.sql").read_bytes().decode("utf-8")`; universal-newline text
reads can rewrite line endings inside quoted manifest strings. The checksummed
binary upload and checkpointed splitter retain those original bytes.

The initial local database is 460,959,744 bytes and the SQL is 286,806,509 bytes;
the receipt is authoritative for subsequent builds. The builder refuses a
database over its conservative 490 MB budget. Actual account import/storage
limits still apply. For large-file import resets, use the statement-aware
checkpointed splitter documented in [D1 import parts](../docs/d1-import-parts.md); never mark a partial import ready manually.

`--events-only` explicitly omits country values for an event-only build; it does
not synthesize missing data. Counts and capabilities report the actual contents.

## Serve the same API with local SQLite

The local adapter requires Node.js with `node:sqlite` (tested with Node 24.19).
It opens the database read-only and only accepts prepared `SELECT` statements:

```sh
node cloudflare/local-api.mjs --database output/research-db/research.sqlite3 --port 8790
```

To serve an already-built site and its API at the same local origin:

```sh
node cloudflare/local-api.mjs --database output/research-db/research.sqlite3 --assets output/site --enable-api-ui --port 8790
```

`output/site` is the directory containing `observations/`. The explicit
`--enable-api-ui` option adds a connection descriptor only to the served atlas
manifest; it never rewrites disk snapshots. Local status identifies
`backend:"sqlite"`, `runtime:"sqlite-local-adapter"`. This is a development
adapter, not evidence of a remote D1 connection.

The original database remains usable without this adapter:

```sql
SELECT country_code, event_year, count(*) AS records
FROM events
GROUP BY country_code, event_year
ORDER BY country_code, event_year;

SELECT json_extract(record_json, '$.attributes.source_article') AS provider_citations
FROM events WHERE id = 'ucdp-ged:26.1:608984';
```

## API contract · `policy-research-db/1`

Only `GET` is supported. All request values use prepared-statement bindings.
Unknown/duplicate parameters, invalid calendar dates, reversed intervals,
unsupported codes, oversized text, and mismatched cursors are rejected. There
is no arbitrary SQL, URL fetch, ingestion, model call, or write endpoint.

| Endpoint | Parameters and response |
| --- | --- |
| `/api/research/status` (`/health` alias) | Actual binding/schema/readiness probe; snapshot, counts, countries, capabilities and limits |
| `/api/research/events` | Required `country`, `from`, `to`; optional `actor`, `type`, `precision`, `date_precision`, `limit`, `cursor`, `count=exact\|none` |
| `/api/research/events/{encoded-id}` | Full original 49-field event, dataset and server-supplied source provenance |
| `/api/research/aggregates` | Same event filters without pagination; year/category counts and bounded two-degree coordinate bins |
| `/api/research/indicators` | Required `country`, `indicator`; optional `from_year`, `to_year`, `limit`, `offset` |
| `/api/research/sources` | `q`, `type`, `limit`, `offset`; unchanged qualified source profiles |
| `/api/research/datasets` | Dataset metadata, licences, original archive/source identities |
| `/api/research/lenses` | Curated PROV-O, SKOS, OWL-Time, GeoSPARQL and SOSA/SSN mappings |
| `/api/research/provenance` | Snapshot manifest identities and stored manifest-chunk counts |

An available status returns HTTP 200 with `status:"ready"`,
`api_version:"policy-research-db/1"`, `schema_version:1`, `read_only:true`,
`backend:"d1"` in Workers or `backend:"sqlite"` in the local adapter. A missing
binding returns HTTP 503 with `status:"unconfigured"`, `backend:"none"`, and
`error.code:"DB_UNCONFIGURED"`. Failed/incomplete imports return a 503
unavailable response. A status request does not turn an unavailable database
into a static result.

Event filters require one uppercase regional country code and explicit real ISO
days; a record matches if its original interval overlaps the requested interval.
Each request covers at most six calendar years. Before scanning events, the API
uses offline-built `policy-query-bounds/1` metadata to reject a conservative
candidate set above 20,000 records. Those counts include whole start-years and
the longest retained interval, so they can exceed the actual number of matches.
Narrow dates or use the static snapshot for broader historical exploration.
The regional allowlist currently contains EG, IL, IQ, IR, JO, LB, PS, SY, TR and YE;
availability still depends on the imported snapshot. Expanding it is a reviewed
code/data change, not an arbitrary-country ingestion endpoint.

The builder measures every original interval and counts records by `date_start`
year. A snapshot-bound maximum duration gives the indexed predicate a safe lower
`date_start` bound while retaining cross-year overlaps. No assumption that the
provider's `event_year` equals the start year is required. Metadata must match
the snapshot identity and event count. A legacy database without these bounds
reports `capabilities.events:false` and `capabilities.aggregates:false`; event
queries fail with `DB_QUERY_BOUNDS_REQUIRED` before scanning the event table.
The prepared upgrade SQL changes only that metadata, conditional on the existing
snapshot ID, event count and ready marker. Review it separately and verify the
result when remote work is authorized; never run it during quota exhaustion.

Violence types are 1–3, geography precision codes 1–7, and date precision codes
1–5. Actor search is a literal lowercase substring of the two provider side
names, at most 200 Unicode characters; `%` and `_` are not wildcards. The date
order is `date_start DESC, id DESC`. Opaque cursors bind that order to the exact
filters and snapshot; they are pagination tokens, not authorization tokens.

Event responses supply `records`, `matched`, `returned`, `limit`, `next_cursor`,
`has_more`, `page_scope:"current_page"`, and `bounded:true`. `matched` is the
whole filtered count before the cursor when `count_scope:"exact_query"`.
The first page defaults to `count=exact`; continuation pages default to
`count=none`, returning `matched:null` and `count_scope:"not_requested"`.
Clients needing an exact total on a continuation may explicitly request it.
The atlas retains its first exact total only for the same query fingerprint,
filters, backend and snapshot. A count is never taken from an unsigned cursor.
`returned` is at most 200, and
`truncated` means this response does not contain every match. `has_more` controls
continuation; with no requested count, a continuation is conservatively marked
truncated. Compact records contain the same 15 plotting fields as the static
atlas and a same-origin `detail_url`; they do not reuse static `raw_shard` URLs.

Detail provenance identifies the validated source manifest, original source
partition and canonical original-field digest. That digest is supplied by the
server. Recomputing it checks field consistency; it is not an independent
browser attestation against the static asset manifest. Static mode retains its
separate gzip/decoded-file/row integrity checks. Annual values remain separate
country-level context with their original units/statuses and methodological
qualifications. Coordinate bins count source points, omit missing/invalid
locations explicitly, and do not represent control areas or precise locations.

Aggregates use one indexed scan grouped by year, category and coordinate bin,
then derive all views from those same groups. Results above 10,000 groups are
refused without partial totals. Snapshot metadata and dataset descriptions are
cached for 60 seconds per binding in the current Worker isolate; aggregate
values have the same TTL and a maximum of 16 entries. No identity, annotations,
Request/Response object or I/O promise is retained. These caches are not durable
and do not establish a global read limit. Invalid routes, parameters, date
windows and malformed/query-mismatched cursors are rejected before D1 is used.

### Daily quota exhaustion

A recognized D1 daily/free-tier quota error returns HTTP 503 with
`error.code:"DB_QUOTA_EXHAUSTED"`, `Retry-After`, and `retry_at` set to the next
UTC midnight. Provider error text and query values are never returned or logged.
The current isolate stops retrying that binding until then; other isolates can
still receive the first error. The atlas also stores only the reset time in
per-tab session storage and suppresses repeated requests, including after a
reload. It does not store search terms there or silently display static rows
as a failed database query. The user must choose Verified static snapshot.

Opening the atlas in static mode makes **zero API probes**, even when a binding
is configured. Selecting Database performs the first status check. Generic
outages remain retryable and are not mislabeled as daily quotas. A reset time
is not a promise that the service will be ready or authorization to run imports,
paid services or automatic collection.

## Existing private Cloudflare Worker

The repository's default `wrangler.jsonc` is assets-only, binds no database and
disables workers.dev and preview URLs. It cannot enable the private API. Keep
private desk databases, case exports, SQL imports and credentials outside any
static output directory. The local adapter rejects database/dotfile requests and
symlink escapes; it still binds only to loopback and is not a hosted auth layer.

The dependency-free ESM module is `research-worker.mjs`; its only export is the
default Worker handler. Bind `RESEARCH_DB` as D1 and `ASSETS` as static assets.
Set the non-secret `PRIVATE_HOSTNAME` to the exact protected hostname. Non-local
API and connected-manifest requests fail closed if the configured hostname is
missing or different. Requests from another Origin are refused and no CORS
permission is added.

[binding-metadata.example.json](binding-metadata.example.json) describes the REST
upload metadata shape; its placeholders are not deployable credentials. Merge
the bindings and routes into the existing deployment configuration, preserving
its assets headers/redirects and existing Access application. In an existing
Wrangler project, the corresponding D1 binding is:

```json
{"d1_databases":[{"binding":"RESEARCH_DB","database_name":"YOUR_DATABASE","database_id":"YOUR_UUID"}]}
```

Run the user Worker first for `/api/research/*` and these exact manifest paths:

```text
/api/research
/tools/middle-east/observations/data/manifest.json
/observations/data/manifest.json
/tools/tacitus-context/semantic/manifest.json
/semantic/manifest.json
```

Atlas paths must have `policy-observation-atlas/1`; Workbench semantic paths must
have `tacitus-semantic-explorer/1`. A different format at an allowed path is
rejected rather than being rewritten. Other paths are never rewritten.

Only with a bound database, the Worker adds
`query_api:{"enabled":true,"base_url":"/api/research"}` to that served manifest.
It reads at most 2 MiB, preserves every shard/catalogue hash, removes stale
conditional/length/encoding headers, and returns `private, no-store`. The status
probe remains the authority on actual connection availability. Without a binding,
the manifest is passed through unchanged. NativeSites and other static mirrors
retain their static manifests and can link to the protected connected host.

**Cloudflare Access must protect the entire hostname, including API and asset
paths; preview URLs must remain disabled.** The hostname check is an additional
routing restriction, not authentication. The Worker does not trust unsigned
Access-header presence or `ctx.access`; the Static Assets router does not pass
that context to user code. No Access audience/policy is changed by this module.
Import/binding/deployment are deliberate operator actions outside the HTTP API.

## Verification

```sh
python -m unittest discover -s tests -p test_research_database.py -v
node cloudflare/worker.test.mjs
node scripts/check_research_query_budget.mjs output/research-db/research.sqlite3 output/query-review.json
```

The builder tests cover exact source fields, Unicode/apostrophes, manifest
reconstruction, deterministic SQL, foreign keys, corruption, bounded statements
and refusal to overwrite. Worker tests cover cursor/filter semantics, injection
text, null-coordinate coverage, source details, private-host/same-origin checks,
read-only methods, incomplete imports and bound/unbound manifest injection.

The complete SQL was replayed locally with foreign keys enabled and every table
compared with the baseline. The actual installed Wrangler/workerd D1 binding was
also tested using a clearly marked real-data subset (40 events, 66 annual values,
55 source profiles, five lenses). That runtime test is separate from full-volume
SQLite validation and from remote deployment. Remote readiness must be checked
after the actual account import. No code path substitutes a successful local
test for that check.

References: [D1 prepared statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[Workers Static Assets routing](https://developers.cloudflare.com/workers/static-assets/routing/advanced/),
[Access with Workers](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
