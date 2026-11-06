# Historical event provenance and refresh

The historical atlas uses a finite, redistributable selection of **120,576 real
UCDP GED 26.1 records**, covering provider years 2000–2025. It is a historical
research collection, not a current operational feed or a complete inventory of
violence. No model-generated observations or synthetic padding are included.

## Official source and rights

The [UCDP download center](https://ucdp.uu.se/downloads/) identifies Global GED
26.1 as the stable release and states that its datasets are available under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The untouched download,
codebook, license receipts and hashes were verified on 2026-11-05. The bulk ZIP
returned HTTP 200 without credentials; the token-based API and monthly candidate
release were not used.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| [Official CSV ZIP](https://ucdp.uu.se/downloads/ged/ged261-csv.zip) | 39,122,522 | `8c941d84954e555ee2e54f40fa04d9203bf1e2f962203d0a9930966c4947c667` |
| `GEDEvent_v26_1.csv` inside ZIP | 273,992,720 | `61c3bf0a86374778343ba30c28a18b1fe739e2c33a76055504427eded4f8be27` |
| [Official codebook](https://ucdp.uu.se/downloads/ged/ged261.pdf) | 917,038 | `f767380ebbf365aec7586f98b6d100cafb69fb54010a908604d53bd9ad655972` |

The full provider release contains 417,968 records and 49 CSV columns. The
committed snapshot preserves **all 49 original string values** in separate full
record parts. Bibliographic source fields and headlines remain metadata; original
news article bodies have not been fetched or redistributed.

Attribution is retained in dataset metadata and exports:

- UCDP GED Global version 26.1, Uppsala University.
- Davies, Pettersson and Öberg (2026), *Organized violence 1989–2025, and violent
  political protests*, [DOI](https://doi.org/10.1093/jopres/xjag046).
- Sundberg and Melander (2013), *Introducing the UCDP Georeferenced Event
  Dataset*, Journal of Peace Research 50(4), 523–532.
- Högbladh (2026), *UCDP GED Codebook version 26.1*.

This is a modified distribution: selected provider countries and years,
whole-record publication-scope filtering, normalized index fields and deterministic
sharding. Retained source values are unchanged; provider endorsement is not implied.

## Selection and geographic coding

The selection uses the provider's `year` field from 2000 through 2025 and exact
country labels below. Lookup codes support navigation; they do not change evidence
labels or assert boundaries or legal status.

| Exact provider label | Lookup code | Retained records |
| --- | --- | ---: |
| Syria | SY | 88,284 |
| Iraq | IQ | 9,030 |
| Lebanon | LB | 1,791 |
| Israel | IL | 11,187 |
| Jordan | JO | 8 |
| Egypt | EG | 824 |
| Yemen (North Yemen) | YE | 6,103 |
| Iran | IR | 687 |
| Turkey | TR | 2,662 |

The provider `Israel` category includes locations coded in Gaza and the West Bank.
There is no separately invented country series. Inspect original `country`,
`adm_1`, `adm_2`, location and precision fields before making geographic comparisons.

Of 120,936 finite regional candidates, 360 entire records were excluded by
publication scope. A decoded screening view is checked across every source field;
the original retained field values are never redacted. The public manifest gives
the method and count without publishing excluded text. The archive and provenance
documents remain untouched for audit and are not copied to the static site.
An omitted observation is not evidence that no event occurred.

## Precision and estimates

Coordinates are not uniformly precise. `where_prec` distinguishes exact named
locations (1), within 25 km of a known point (2), administrative-area representative
points (3–4), linear or informal areas (5), country-only locations (6), and estimated
sea or air positions (7). `date_prec` distinguishes a day (1), a two-to-six-day
range (2), a week (3), eight-to-thirty days or a month (4), and a longer period
within a calendar year (5). All labels and original codes are included in metadata.

The normalized start/end dates retain the original date window. Midnight strings
in the original fields are not precise timestamps. `event_clarity=2` means
aggregate reporting not fully disaggregated; 1 identifies an individual event.
`type_of_violence` retains state-based (1), non-state (2) and one-sided (3) coding.

**Low, best and high are provider estimates, not confidence intervals.** There
are 683 observations where they are not ordered. Their exact values are preserved
and flagged `provider_estimates_not_ordered`. The codebook's discussion of aggregate
subtraction does not explain every individual case; no blanket cause is inferred.
There are 2,099 aggregate
records overall, independently flagged `aggregate_reporting`.

`code_status=Clear` is the provider's coding status, not a new review or guarantee
of truth. A historical `number_of_sources=-1` is an availability convention, not
proof that no source existed. Actor names and modern actor identifiers are retained;
no political allegiance, control or confidence score is inferred.

## File and integration contract

The snapshot is `data/historical/ucdp-ged-26.1/`. It contains `manifest.json`, 297
compact parts under `events/`, 297 matching full parts under `events-raw/`, and
archival-only `provenance/`. Country/year parts are sorted by numeric provider ID.
Every source JSON asset is at most **1,572,864 bytes**; the actual largest is
1,572,830 bytes. Source compact records total 98,161,044 bytes; full records total
228,461,716 bytes. These immutable source parts remain uncompressed in the
repository, independently of the smaller static hosting package.

`build_static_bundle(repository: Path, output: Path)` in
`src/syria_analysis/historical_events.py` validates every compact/full join and
publishes compact JSON plus **gzip-compressed full-record parts**. It returns a
`policy-observation-atlas/1` manifest fragment for the main builder. It does not
copy the global ZIP, codebook, HTML or provenance documents.

Gzip uses an empty filename, zero modification time and a fixed compression level
through `GzipFile`; identical input produces identical asset bytes without a
platform-specific OS header. There is no uncompressed duplicate of the served
full-record parts. Country/year pairs are repartitioned if the longer `.gz`
references would exceed the byte budget, so served part counts may differ from
the immutable source. Every served compact JSON part and every decoded full JSON
part remains at most 1,572,864 bytes. Record count, source values and record digests
are unchanged. Build into a fresh output directory; a legacy uncompressed evidence
part or a changed existing asset is refused rather than overwritten.

Each event has a versioned stable `id`, original `provider_id`, dataset ID,
provider country label, lookup code, original date window, coordinates,
`source_locator`, `raw_record_sha256`, `quality_flags` and `raw_shard`.
Compact `attributes` contain 15 plotting/interpretation fields. The matching full
record contains all 49 original CSV fields. `raw_shard` resolves relative to the
atlas root, e.g. `./data/events-raw/SY/2020-001.json.gz`; join on `id` and verify
`raw_record_sha256`. The digest uses sorted-key, compact UTF-8 JSON of all 49
original string values, with `ensure_ascii=False`.

The served manifest lists every part's count, byte size, SHA-256, country,
provider-year partition and actual date bounds. Compact `event_shards` hashes
describe the amended JSON bytes. Each `raw_shards` entry has `encoding: "gzip"`;
its `bytes` and `sha256` describe the compressed asset, and `decoded_bytes` and
`decoded_sha256` describe the exact uncompressed wrapper. Verify compressed bytes
before decoding, bound decompression to the declared limit, then verify decoded
bytes and hash before parsing. The `.json.gz` files are explicit data assets, not
an HTTP `Content-Encoding` instruction. The per-record canonical digest still
checks the original 49 attributes after decoding.

Initial Syria 2020–2025 plot loading contains 5,263 records, about 4.3 MB of compact
JSON; full evidence can be fetched only for inspection/export. Compression changes
the hosting package, not the historical selection or its uncertainty.

## Reproduce and refresh

Use Python 3.11 or newer. From the repository root, create/install the development
environment as described in the main README, then download the official stable
archive to a local archival location. Preserve its HTTP receipt and original bytes.
The ingestion command rejects a changed ZIP, CSV member, header or existing output.

```sh
PYTHONPATH=src .venv/bin/python scripts/ingest_historical_events.py \
  --archive /absolute/path/to/ged261-csv.zip \
  --output /absolute/path/to/new-snapshot
```

The current committed output cannot be silently overwritten. For a future release,
review the official release notice, codebook, license, source schema, original
country labels, precision categories and any changed semantics first. Use a new
dataset/version directory and pinned hashes. Rebuild rather than mixing releases.
The pipeline uses a temporary SQLite spool, stable provider-ID ordering, atomic
directory creation and bounded parts; data-part bytes are deterministic. `built_at`
records when the snapshot was created and is intentionally not a source date.

Focused checks, including full retained-snapshot integrity:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_historical_events.py -v
.venv/bin/python -m ruff check src/syria_analysis/historical_events.py scripts/ingest_historical_events.py tests/test_historical_events.py
```

The small test fixture contains nine verbatim provider rows, attributed to this
release. Deliberately invalid in-memory test cases are never included in served data.

## Coverage expansion recorded on 2026-11-06

The same pinned official release was expanded from provider years 2011–2025 to
2000–2025. This added 6,920 retained records; no existing observation was rewritten.
All 456 prior compact/full source parts were checked byte-for-byte against their
existing manifest hashes and retained unchanged. The new source manifest SHA-256 is
`522512b06f95616b86aa0448da0505aae6f2106d007efe3ae7f264ee0c0f24b0`.
Earlier dated verification receipts describe the earlier coverage, not a rerun of
the expanded snapshot. The [semantic catalog](semantic-catalog.md) adds bounded
navigation and lazy field alignment while reusing these immutable records.
