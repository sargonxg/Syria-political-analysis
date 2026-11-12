# Historical briefing compiler

Turn an explicitly scoped historical query into a source-linked briefing worksheet,
a bounded JSON context packet and an independently hashable receipt. This is a
runnable preparation tool for policy/research work, not a generated policy assessment.

## Run locally

Node 24+ and Python 3.11+; no model account, paid API or additional Node dependencies.

```sh
git clone https://github.com/sargonxg/Syria-political-analysis.git
cd Syria-political-analysis
PYTHONPATH=src python scripts/build_research_database.py --output output/research-db
node cloudflare/briefing-cli.mjs --database output/research-db/research.sqlite3 --country SY --from 2014 --to 2016 --budget 16000 --output output/syria-brief
node --test cloudflare/briefing.test.mjs
node scripts/benchmark_briefing.mjs output/research-db/research.sqlite3 output/benchmark.json
```

On Windows, install the package with `python -m pip install -e .` before the
builder instead of setting `PYTHONPATH`. Output directories must be new.

Outputs are `context.json` (exact compact payload), `brief.md` (a source-linked
worksheet), and `receipt.json` (SHA-256, exact payload bytes, selected/omitted
counts and the budget boundary). The [committed worked example](../examples/historical-briefing/)
uses the real historical Syria 2014–2016 selection: 37,559 matching provider
records, five complete records in a 16,000-byte budget. The retained evidence
is deliberately small and is not a comprehensive representation of the conflict.

## What the compiler does

1. Validate the database readiness marker, country, real year range, task and byte budget.
2. Query the whole matching interval, retaining overview counts and precision distributions.
3. Consider up to 128 deterministic representatives, stratified by month/violence
   category, recorded side pair, or original location/date precision, depending on task.
4. Greedily pack complete source records without exceeding the exact UTF-8 JSON budget.
5. Recompute each selected record's canonical 49-field provider digest. Refuse
   export if a selected record is corrupted.
6. Emit the packet, human-review worksheet and checksum receipt.

`--task background`, `--task actors` and `--task quality` choose the three
structured selection modes. `--question` records an analyst-supplied task label
up to 300 characters; it is not semantic retrieval or model reasoning. SQL
parameters are bound. Date intervals overlap the requested window; a coarse
source interval can extend beyond it. Empty queries produce an explicitly empty
worksheet. If no complete record can fit, compilation refuses instead of emitting
an apparently successful evidence-free context.

All 49 original provider fields, source citations, precision codes, snapshot ID,
source-manifest hash, explicit omissions and `not_reviewed` state remain in the
packet. Analyst assessment stays null. Selected/omitted counts describe the
whole query; at most 128 candidate IDs are considered, and the receipt separately
counts unconsidered matches and candidates excluded by packing. The budget
covers the compact JSON payload, not the separate Markdown/receipt overhead.

This format is `tacitus-historical-brief/1`. It is separate from native TACITUS
capsules, Context JSON readers, and PRAXIS imports. No conversion is implied.

## Worker / Cloudflare integration

`cloudflare/briefing.mjs` is a dependency-free ES module. Pass a read-only-style
D1 binding to `compileBrief(db, parseOptions(url.searchParams))`. It uses only
prepared SELECT statements and D1 `batch`, matching the existing local SQLite
adapter. `overview(db, params)` produces bounded quarter-degree coordinate bins,
annual counts and top recorded side pairs for a linked visualization.

The caller must enforce whole-host authentication, same-origin requests, input
limits and explicit error states. Do not put the module behind a public endpoint
or treat a hostname/header-presence check as authentication. The company preview
uses Cloudflare Access plus independently validated signed Access assertions on
pages, assets and API routes. The compiler contains no HTTP write endpoint.

The additive migration in
[002_interval_covering.sql](../cloudflare/migrations/002_interval_covering.sql)
creates a covering country/interval index. It changes no provider records and
leaves API schema version 1 intact. Fresh database builds include the index.
Apply deliberately to an existing D1 database through the operator's configured
deployment path; the compiler never creates it on a user request.

## Executed benchmark

[Full results](../examples/historical-briefing/benchmark.json) retain all six cases
and all 18 packing runs. The performance comparison uses the same exact query,
filters and full 120,576-event database across a covering index, the former index
forced with `INDEXED BY`, and a full scan forced with `NOT INDEXED`.

Each arm gets one warm-up and 20 measured repetitions; execution order rotates.
The host has warm OS caches. In the Syria 2014–2016 case, local p50 count time
was 5.01 ms with the covering index, 65.57 ms with the old index and 75.87 ms for
a full scan. Counts matched in all six cases. Very small queries can favor the
old index; inspect the complete results rather than treating one ratio as universal.

All 18 budget/case combinations were deterministic, within their byte ceiling
and exactly matched the selected database records. These are structural checks,
not held-out diplomatic usefulness tests. Compilation latency is recorded as a
single observation per case/budget, separately from the repeated count benchmark.

The [remote D1 check](../examples/historical-briefing/d1-query-check.json) records
one SQL-duration observation per case before/after the additive index. For the
same Syria query it recorded 217.44 ms before and 9.35 ms after, with the same
37,559 records. These are server SQL durations, not repeated end-to-end latency
measurements. Network time, model tokens, inference cost and answer quality were
not measured. No model was called.

## Limits and business use

Use the worksheet to prepare a historical evidence baseline, review provider
recorded actors, or expose evidence-quality questions before a policy discussion.
It does not establish current control, cause, alliance, negotiating mandate,
consent, representation or a recommended intervention. Those tasks need other
sources and accountable analyst review.

Third-party observations retain their original attribution and licensing in
the packet. Checksums establish byte consistency with the retained dataset, not
independent truth or publisher authentication.


## Cross-backend compilation check

The same compiler was executed against the real Cloudflare D1 database and the
local full-volume SQLite build for the default Syria 2014–2016 task. Both returned
the same 14,851-byte context and SHA-256
`79c567ff545622b85ad1e7664b3c0bc69dfa4662e8181bf7fa9bf38ffe2a71f7`.
The [remote receipt](../examples/historical-briefing/remote-compiler-check.json)
records five complete provider records selected from 37,559 matches. This checks
cross-backend output fidelity, not hosted sign-in or analyst usefulness.
