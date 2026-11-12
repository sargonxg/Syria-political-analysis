# Historical change brief

Compare two disjoint calendar-year windows in the retained UCDP GED 26.1 collection. This is a runnable preparation tool for a policy/research briefing: exact period counts, annualized counts, recorded-side comparisons, provenance, selected source evidence, and an editable Markdown review worksheet.

It does not infer conflict intensity, causality, current control, negotiating representation or consent. A change in provider observation counts can reflect reporting and coverage changes as well as events.

## Run locally

Node 24+, Python 3.11+, and this repository's committed snapshot are sufficient; no model/API account is required.

```sh
python -m pip install -e .
python scripts/build_research_database.py --output output/research-db
node cloudflare/change-brief-cli.mjs --database output/research-db/research.sqlite3 --output output/change-brief --country SY --baseline_from 2011 --baseline_to 2013 --from 2014 --to 2016 --budget 16000 --mode compact
```

Use a new output directory. The CLI refuses to overwrite an existing directory and opens SQLite read-only. Outputs are `context.json`, `change-brief.md`, and `receipt.json`. The worksheet leaves the analyst assessment pending.

## What the compiler does

1. Validate country, disjoint full-calendar-year intervals, representation mode, and an 8,000–64,000-byte payload budget.
2. Query the ready database with prepared SELECTs. Compare exact interval-overlap counts, provider-year counts, location-precision distributions, and up to twelve most frequent recorded-side pairs across both windows.
3. Retrieve up to 64 structured representatives per period, stratified by provider month and violence type.
4. Interleave the periods, verify each candidate's canonical original-field SHA-256 and envelope, then pack complete evidence items within the exact UTF-8 JSON budget.
5. Refuse a nonempty comparison if evidence from either period cannot fit. Export an inspectable packet, checksum receipt and Markdown worksheet.

A long source interval can overlap both windows. The compiler counts that overlap explicitly and stores a shared source item once with both memberships. Omission counts are scope memberships, not a count of unique sources.

The question is a retained task label, not semantic retrieval. Candidate limits and deterministic packing are explicit, and more retained records does not prove greater analytical relevance.

## Compact and full evidence

`--mode full` retains the complete provider record, including all 49 original attributes.

`--mode compact` retains the source ID, original dates, original-record URL and field digest plus these ten task fields: `side_a`, `side_b`, `type_of_violence`, `where_coordinates`, `adm_1`, `where_prec`, `date_prec`, `source_article`, `source_headline`, and `source_date`. The original record remains available in the database and through the protected research-detail API. Compact evidence is an explicit projection, not an unchanged original export. Reuse outside the company site must resolve the relative original-record URL against its own research API origin.

Provider dataset metadata, source manifest identity, precision distributions, coverage qualifications, unreviewed status and omission counts travel inside the budgeted packet. A checksum establishes consistency with this snapshot, not independent corroboration or trusted authorship.

## Benchmarks

```sh
node --test cloudflare/comparison.test.mjs cloudflare/briefing.test.mjs
node scripts/benchmark_comparison.mjs output/research-db/research.sqlite3 output/comparison-benchmark.json
```

The committed [comparison report](../examples/historical-briefing/comparison-benchmark.json) uses the full 120,576-record SQLite snapshot: six developer-visible comparisons × three budgets × two evidence modes. Each successful arm has one warm-up and three measured compilations, deterministic byte equality, exact source-field checks and independently checked SQL counts. Refusals are recorded.

For the Syria 2011–2013 versus 2014–2016 example, a 16,000-byte budget retains 11 compact records versus 3 complete records. Compact context is 15,929 bytes. These are packing/structural measurements, not token savings, model-answer quality or diplomatic outcomes. Host timings are not Cloudflare latency; three measured samples are descriptive.

[Worked output](../examples/historical-briefing/change/context.json) · [Worksheet](../examples/historical-briefing/change/change-brief.md) · [Receipt](../examples/historical-briefing/change/receipt.json)

## Cloudflare and the company interface

`comparison.mjs` takes the same prepared-statement D1 interface as the existing compiler. Bind the existing verified research database in an owner-private Worker. The company interface exposes read-only `/api/desk/compare` for the comparison chart and `/api/desk/change-brief` for compilation; request arguments match the CLI except `database` and `output`.

This repository's standalone research Worker remains unchanged. The company handler composes the compiler with its own private authorization boundary. Do not expose a database or alternate preview route to make a demo work. No database writes, import/reindex operation, model call or persistent question storage is added by this pipeline.

