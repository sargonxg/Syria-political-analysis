# Historical research atlas

A reproducible Middle East data workspace: **120,576 UCDP GED event records for 2000–2025**, plus **15,272 non-null annual World Development Indicators values**, 32 indicators and ten economies. The event collection has nine provider country categories; annual country context also includes the World Bank's West Bank and Gaza category. These are separate source classifications, not a border determination or an inferred join.

The map and time filter operate on compact point partitions. Selecting a record retrieves its complete 49 original UCDP fields. Full records, codebook precision, dates, fatality estimates and source locators remain attached. Static builds store the detailed partitions as lossless gzip JSON; browser and CLI verify both compressed and decoded identities before reading them. The source snapshot remains plain, immutable JSON. The recorded-sides view counts provider side-A/side-B pairs; its lines do not establish affiliation or current relationships. A paginated directory provides the same record selection without relying on a map.

Country series are shown separately with their units, definitions and available years. Missing values stay missing: 5,848 returned null rows are documented in coverage metadata rather than drawn as zero. Genuine zeros remain numeric values. Historical estimates and modelled values retain source qualifications; no interpolation or forecast is generated.

## Run from a clean checkout

Python 3.11+ and Git are enough. The build uses the committed snapshots; it makes no network collection requests or model calls.

```sh
git clone https://github.com/sargonxg/Syria-political-analysis.git
cd Syria-political-analysis
python -m pip install -e .
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Open **http://127.0.0.1:8766/observations/**. The original source directory and curated political-context desk remain at `/sources/` and `/`. A server is needed for same-origin JSON requests; opening this multi-file atlas through `file://` is not supported. The older single-file source atlas is still available through its existing command.

To build only the historical atlas:

```sh
policy-analysis build-observations --output dist/observations
```

## Three useful tasks

### Inspect a claim about changing conflict geography

Select Syria and a bounded year range, then compare provider categories and location precision. Follow a dense area to individual records; inspect dates, original citations and geographic uncertainty before writing a geographic conclusion. An event count is a count of this dataset's records, not an estimate of all violence, a current control map or an independent accuracy assessment.

For a reproducible source selection:

```sh
policy-analysis --country SY research-query \
  --from-year 2024 --to-year 2025 \
  --violence-type 1 --geography-precision 1 --limit 12 \
  --question "What do precisely geocoded state-based records establish about Syria in 2024–2025?" \
  --output output/syria-events.json
policy-analysis validate-selection output/syria-events.json
```

The committed [worked selection](../examples/historical-research/syria-events.json) contains the first 12 chronologically sorted matches of 323, with the omission count explicit. It is a real provider-data example, not a fictional event scenario. Source classification and precision are retained; no analyst conclusion is prewritten.

### Check the temporal basis of a recovery brief

Open the annual-country panel and choose constant-price GDP. In this snapshot Syria's available annual values stop at **2022**; internet use stops at 2018, CPI inflation at 2019 and FDI at 2011. An event in 2025 does not turn an older economic value into a 2025 estimate.

```sh
policy-analysis --country SY research-query \
  --indicator NY.GDP.MKTP.KD --from-year 2011 --to-year 2025 \
  --question "Which GDP estimates are actually available, and where does the series stop?" \
  --output output/syria-gdp.json
```

The [country-context example](../examples/historical-research/syria-country-context.json) exports all 12 available values for 2011–2022. Event-specific actor, violence and geographic-precision filters are refused in this mode. Comparing dates and country labels does not identify a causal effect of conflict on GDP.

### Hand off a bounded research packet

Write a research question, assessment, alternative and evidence gaps; download the selected source rows. Open the JSON in [TACITUS Workbench's research-selection reader](https://github.com/sargonxg/tacitus-workbench). The reader inspects these records and re-exports the original imported bytes.

`policy-research-selection/1` is a separate contract from `policy-context-layers/1` and `tacitus-uploaded-knowledge-context/1`. It does not create a native capsule, generate an answer or attach records to PRAXIS. A maximum of 200 records and 1 MiB keeps a handoff inspectable; matched/exported counts and truncation are explicit. Full raw partitions remain available as ordinary JSON assets.

For an AI-assisted briefing, provide the selection and ask the model to cite record IDs and original fields, distinguish provider reporting from analyst interpretation, state missingness and test alternatives. Independently check important assertions against the cited material. Dataset metadata, a graph connection or a successful schema check does not establish a political conclusion.

## Data and ontology contracts

- `policy-observation-atlas/1` describes dataset metadata, country categories, compact event shards, exact raw partners and annual indicator shards.
- [research_selection.schema.json](../schemas/research_selection.schema.json) defines the bounded interchange envelope. `research_selection.py` additionally checks resolved IDs, counts, real ordered dates, finite values, depth and byte limits.
- [Observation vocabulary](../ontology/observations.jsonld) documents the difference between a dataset record, its precision/period, a provider attribution and an analyst assessment. It is a vocabulary, not an extraction engine or an automatic mapping to political claims.
- The existing [Syria political ontology](political-ontology.md) remains a separate curated model of political concepts and qualified normative statements. The historical events are not silently promoted into reviewed political assertions.

## Storage, provenance and deployment

The snapshot contains 228 compact event shards and 228 matching full-record shards. Each event asset is at most 1.5 MiB. Country-series partitions use the same size boundary. Manifest SHA-256 values identify each file; original archive/API receipts and per-indicator licences are retained in the repository. The static build screens served data and does not include the original global archive, private notebook data or the source codebook PDF. Official publications remain linked.

Deploy the built `dist/` through the existing `wrangler.jsonc`, or copy it to a static host. The personal site's owner-only Cloudflare preview serves the same snapshots under `/tools/middle-east/observations/`. Existing Access protection must remain in place for that private preview. No D1 database, R2 bucket, scheduled collector, paid model provider or public API is required. Native Static Assets hold both the application and its partitioned data.

Dataset metadata and source documentation retain their own licences. UCDP GED 26.1 is CC BY 4.0, with the required publication/codebook attribution and an explicit modified-distribution note. The selected WDI series each declare CC BY 4.0 in their metadata; World Bank dataset terms and original-provider attribution also apply. Generalized land geometry is Natural Earth public-domain data. Code remains MIT.

See [historical-data provenance](historical-events.md) and [country-context collection](country-context.md) for refresh procedures and exact source limitations. Refresh is deliberate: a source release or API revision creates a new dated snapshot; it is not a live intelligence feed.
