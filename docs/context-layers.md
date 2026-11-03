# Context desk: from source to assessment

The context desk is a self-contained view of seven layers: **sources, documents/evidence, political context, ontology, time, analytical method and your assessment**. Select a record to inspect its original data and labelled relationships. Add material to a brief, enter an interpretation and alternative explanation, then export Markdown or the complete JSON context.

The question labels the pack; it does not trigger AI generation or semantic search. The graph shows record relationships. It does not infer political influence, implementation, territorial control or causal relationships. Notes live only in the open tab; download them before closing it.

## Run locally, including offline

From the repository root, with Python 3.11+:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
policy-analysis --country SY context-layers --question "What does resolution 2254 request?" --format html --output exports/context/index.html
```

Open `exports/context/index.html` directly. It contains its own scripts, styles and data; it makes no network requests. On Windows use `.venv\Scripts\activate` instead of the activation line. `--format json` produces the AI-readable contract in [context_layers.schema.json](../schemas/context_layers.schema.json); `--format markdown` produces a source-qualified reading brief without invented analysis.

`--publication-cutoff 2015-12-18` filters **publication dates only**. Unknown dates remain included and disclosed; retrieval dates and political validity are separate. It is not a historical knowledge cutoff. A schema definition is not a political fact, and the six resolution-2254 assertion drafts remain unreviewed normative statements.

The snapshot digest identifies Python-canonical country/record/edge content. It excludes the question, build timestamp and visitor assessment. It is not a signature, proof of external truth or hash of the downloaded file bytes.

## Static cloud build

```sh
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Visit `http://127.0.0.1:8766`. `/sources/` opens the separate source atlas. The build reads the curated country workspace, not SQLite cases or private exports. Inspect `dist/` before uploading it. It contains public data only; it has no authentication, case storage or server-side analysis.

For Cloudflare Workers Static Assets, install Node 22+ and run from this root:

```sh
npx wrangler login
npx wrangler deploy --config wrangler.jsonc
```

This publishes the static snapshot to your account. For restricted access, place the hostname behind Cloudflare Access before sharing it. The existing private desk's access key and SQLite database are not part of this deployment. Cloudflare Pages can instead use build command `python -m pip install -e . && python scripts/build_showcase.py` and output directory `dist`.

Cloudflare configuration follows [Static Assets](https://developers.cloudflare.com/workers/static-assets/) and [asset routing](https://developers.cloudflare.com/workers/static-assets/routing/static-site-generation/). A direct cloud deployment requires your own authenticated account. Repository CI only builds and checks the artifact.

## Extend beyond Syria

```sh
policy-analysis init-country --code LB --name Lebanon --region "Middle East"
policy-analysis --country LB validate
policy-analysis --country LB context-layers --question "What needs primary evidence?" --format html --output countries/lb/exports/context.html
```

A country starts empty. Add its source directory, document receipts and country-scoped political concepts with citations; no Syria claims or actors are copied. See [country workspaces](country-workspaces.md) and [political ontology](political-ontology.md).

For durable private cases, exact-quote capture, revision history and authenticated collaboration by a single operator, use the separate [FastAPI/container desk](deployment.md). Its data model is not interchangeable with this public snapshot contract or TACITUS native contexts.
