# Annual country context from the World Bank

The committed snapshot contains **15,272 non-null annual values** from **32 World
Development Indicators**, for ten explicitly selected economies over 1960–2025.
It complements the conflict-event atlas with economic, demographic, service and
environmental context. It adds no incident locations, displacement corridors or
causal relationships.

Collected on **5 November 2026**. The API identifies the WDI source update as
**8 October 2026**. That is a dataset update date, not an observation’s publication
date or proof of current conditions.

## Coverage actually returned

| Economy, using World Bank labels | ISO2 / ISO3 | Non-null values |
| --- | --- | ---: |
| Egypt, Arab Rep. | EG / EGY | 1,732 |
| Iran, Islamic Rep. | IR / IRN | 1,651 |
| Iraq | IQ / IRQ | 1,562 |
| Israel | IL / ISR | 1,620 |
| Jordan | JO / JOR | 1,630 |
| Lebanon | LB / LBN | 1,373 |
| West Bank and Gaza | PS / PSE | 1,126 |
| Syrian Arab Republic | SY / SYR | 1,611 |
| Türkiye | TR / TUR | 1,720 |
| Yemen, Rep. | YE / YEM | 1,247 |

The API returned 21,120 cells. **5,848 are null** and are excluded from the value
count; 24 genuine numeric zeros are retained. All requested cells were returned,
so the separate unreturned-cell count is zero. No forecast or other nonblank
observation-status flag was present in this captured dataset. The collector would
withhold those flagged values rather than count them as historical observations.

Coverage varies by series and country. Syria has GDP through 2022, internet use
through 2018, CPI inflation through 2019, FDI through 2011 and health expenditure
through 2023. Showing each as a current 2025 value would misrepresent the source.
`coverage.json` retains the first/last value year, null years, unreturned years and
withheld-status years for every country/indicator pair.

## A practical research question

Compare the published service-access and income series for Syria, Jordan and
Lebanon before and after 2011, alongside a separately identified conflict-event
record. Begin with one indicator and its actual years, rather than a composite
“fragility” score.

For example, Syria’s constant-price GDP-per-capita series has a 2022 value but no
2024 value in this snapshot. The chart must leave 2024 empty. Lebanon’s published
electricity-access value for 2024 is 100%; that indicator measures access and
does not establish reliable supply or hours of service. Basic drinking-water
access similarly differs from safely managed water, local quality or uninterrupted
supply. Those distinctions produce useful collection questions for a brief.

Country/year alignment with UCDP records can help a reader navigate the context.
It cannot establish that an event caused a national indicator change. National
values should not be assigned to individual towns, actors or incidents. No
fatality rate, migration corridor or combined political-risk index is derived.

## Source and licensing checks

The connector uses the official [World Bank v2 API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation),
with source `2` (World Development Indicators), explicit economy codes, annual
periods, `footnote=y` and complete pagination. No account or API key is needed for
these requests.

Every selected series returned explicit `License_Type: CC BY-4.0` and a
`License_URL` in its own metadata. The connector refuses absent or unapproved
licences, missing definitions and non-annual/forward-forecast series. This is a
series allowlist, not permission to redistribute every World Bank catalogue.
The [World Bank dataset terms](https://data.worldbank.org/summary-terms-of-use)
include attribution requirements and additional terms, and note that other
indicators can have third-party restrictions.

The snapshot retains each indicator’s original providers, definition, unit,
periodicity, reference period, aggregation method, methodology, limitations and
licence metadata. Attribution travels with the build:

> The World Bank: World Development Indicators: original data providers named in each indicator’s metadata. Retrieved 2026-11-05.

This independent use does not imply World Bank endorsement.

## Measurement and missingness

- Values can be estimates. Population metadata describes midyear estimates; ILO
  employment series explicitly use models. A blank `obs_status` does not establish
  a direct measurement or resolve estimate versus projection at cell level.
- The World Bank documents `F` as a [forecast status](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886674-new-features-and-enhancements-in-the-v2-api).
  The connector withholds `F` and unrecognized nonblank statuses and records those
  years separately. It excludes current/future calendar periods and explicitly
  forecast/projection series. General methodological discussion of projections
  does not turn every historical modeled value into a known forecast.
- Raw values are never rescaled using `decimal`. That field is retained as source
  metadata. Nominal US dollars, constant 2015 US dollars, rates, people and gross
  enrollment percentages remain different measures. Negative values and gross
  percentages above 100 are not automatically invalid.
- Some provider units are blank or generic. The reviewed display unit is derived
  from the indicator name/definition, with that derivation labelled separately;
  the raw provider unit is preserved unchanged.
- No zero imputation, interpolation, last-observation carry-forward or computed
  regional aggregate is used. The source’s aggregation-method metadata documents
  WDI methodology; it is not an instruction to sum country percentages.
- Annual period labels are preserved. Specific stock dates, national-accounts
  periods and fiscal comparability follow each source’s methodology. The year is
  not an incident date or the date the value became knowable.

## Files and reproducible refresh

The snapshot lives under `data/observations/world-bank/`:

| File | Purpose |
| --- | --- |
| `manifest.json` | Counts, dates, scope and SHA-256/byte size for every constituent file. Its own hash binds the atlas dataset entry. |
| `indicators.json` | All 32 definitions, units, providers, licences, methods and interpretive cautions. |
| `countries.json` | Explicit economy labels and ISO2/ISO3 identifiers, without derived event coordinates. |
| `coverage.json` | Country/indicator nulls, unreturned/withheld years and first/last numeric periods. |
| `observations.jsonl` | Non-null numeric values with stable IDs and original flattened provider fields. |
| `countries/*.json` | Normalized country partitions for offline reuse. |
| `receipts.json` | Exact request URLs, retrieval timestamps, response hashes, byte lengths and raw-file paths. |
| `raw/` | The original 42 successful HTTP response bodies, including nulls and complete selected-series metadata. |

Manual collection uses only the Python standard library. It requires a fresh
output directory, bounds response size/time/retries and writes the snapshot only
after all selected requests validate:

```sh
python3 scripts/collect_country_context.py --output /tmp/wdi-refresh-20261105
```

Inspect a proposed refresh before deliberately replacing the committed snapshot.
There is no scheduled refresh, model call or implicit network request at build
time. The fixed default request period is 1960–2025; use the explicit year options
for a separately reviewed historical range.

Example verified API forms:

```text
https://api.worldbank.org/v2/country/SYR;JOR;LBN/indicator/SP.POP.TOTL?source=2&date=1960:2025&format=json&footnote=y&per_page=5000
https://api.worldbank.org/v2/sources/2/series/SP.POP.TOTL/metadata?format=json
https://api.worldbank.org/v2/sources/2?format=json
```

Two live-API findings matter. A multi-indicator response returned `sourceid:null`
even with `source=2`; the connector preserves that header and establishes source
membership through the explicit request and each series’ source-2 metadata.
The legacy refugee-origin/asylum series `SM.POP.REFG.OR` and `SM.POP.REFG` still
returned metadata but their data requests returned API error 120. They are
excluded. No refugee/displacement coverage is advertised or fabricated. The
replacement FDI and industry-value-added series were successfully fetched and
passed their own licence/metadata checks.

## Static observation-atlas connector contract

`build_static_bundle(repository: Path, output: Path)` verifies the committed
snapshot and returns the shared atlas fragment:

```text
datasets: [{id, kind: "country_indicator", title, version, publisher,
            url, license, sha256, coverage, limitations,
            metadata_path, coverage_path, receipts_path, snapshot_path}]
countries: [{code: ISO2, name}]
indicator_shards: [{path, dataset_id, country_code: ISO2, count, sha256}]
limitations: [text]
```

There are 19 numbered country shards, each below 1.5 MiB. **Load every shard
matching the selected country**, not just the first match. Paths are relative to
the atlas root, such as `./data/indicators/SY-01.json`.

Each shard contains `records` with stable ID, dataset ID, ISO2 country code,
indicator code/name, actual year, value, display unit, qualified status, an
original API locator and flat `attributes`. The attributes retain raw provider
fields and explicit `display_unit`, `display_unit_basis`, `interpretation_note`,
`source_status_interpretation` and `source_indicator_metadata` helpers. Those
qualifications survive selection into a reusable context. All attributes are flat
primitives, with at most 128 keys, key length 120, string length 20,000 and
JavaScript-safe numeric magnitudes. No coordinates or relationship edges are
generated.

The separate metadata paths are:

```text
./data/indicators/metadata/indicators.json
./data/indicators/metadata/coverage.json
./data/indicators/metadata/receipts.json
./data/indicators/metadata/manifest.json
```

The dataset SHA-256 is the exact captured snapshot manifest hash:
`2d047fe127c9bc8af9532772be59f69880cf09b4bf45ab90f273a0ba30ed9c09`.
API raw-body hashes and metadata-source hashes remain separately inspectable.

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_country_context.py' -v
```

Ten focused tests pass: null/zero/negative separation, unreturned periods,
forecast/unknown-status withholding, stable IDs, exact values and raw units,
invalid dates/aggregates/duplicates/numbers, licence/forecast refusal, bounded
retries and HTTP-200 API errors, complete pagination, atomic failure, future-scope
refusal, and static shards with provenance and hash-tamper rejection.

The real snapshot build also verified all 15,272 IDs are unique, row counts sum
without null inflation, all 32 licences match their raw metadata, all export
attributes satisfy their bounds, and the largest generated shard is 1,499,737
bytes. No push or deployment is performed by these commands.
