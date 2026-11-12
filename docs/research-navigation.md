# Reopen a research question, not an unexplained dashboard

The historical atlas has two optional starting questions, shareable filter state,
selected-event links and bounded graph views. It uses the same committed historical
snapshots; no live event collection, model service or remote database is required.

## Try a useful starting scope

Build and serve the snapshot from a checkout:

```sh
python -m pip install -e .
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8766/observations/` and expand **Start with a research
question**. The starters change filters and label a question; they do not generate
an assessment or corroborate the provider's reports.

- **Precisely geocoded records:** Syria, 2024–2025, provider violence category 1,
  geographic precision code 1, oldest-first ordering. Inspect the original provider
  fields and codebook before drawing a geographic conclusion.
- **GDP coverage for a recovery brief:** Syria's separate constant-price GDP series.
  Its retained observations end in 2022. The event-period controls do not filter
  this annual series; available dates and missingness remain visible.

Your analyst notes are preserved while choosing a starter. The research-question
field is explicitly replaced by the selected starter question. No answer is
prewritten.

## Share a view and use browser history

Expand **Share & reproduce this view** to copy/open a URL, inspect source identities
and read the corresponding local CLI recipe. Country, interval, recorded actor,
provider category, geographic precision, record search, ordering, view and annual
indicator survive reload. An inspected UCDP event can also be reopened by its exact
provider identity. Browser Back and Forward restore these controls and their data
view. Typing in record search is debounced before a history entry is created.

The link includes the actor and record-search terms. It deliberately excludes the
research question, analyst assessment, alternative explanations and evidence-gap
text. Those notes remain in the current tab and in exports the visitor chooses to
download. They are not put in browser-history state.

Example query state, appended to the atlas URL:

```text
?country=SY&from=2024&to=2025&type=1&precision=1&order=oldest
```

A selected event adds `event=ucdp-ged:26.1:...`. A semantic-index record outside the
current event query can reopen through its `view=lenses&collection=index` state.
If a saved identity is unavailable in the bounded source view, the atlas says so
and never substitutes a different record. A selected-record export with no record
stays empty and disabled, instead of widening to the whole query.

Only known countries and bounded years, categories, precision codes, views and
record-ID forms are accepted. Actor/search fields are limited to 200 characters;
control characters, duplicate parameters and oversized query strings are rejected
or ignored with a visible notice. Years are constrained to the selected country's
retained coverage. No query parameter can supply an external API URL or opt into
remote database access.

**A shared link opens the verified static snapshot.** An existing database view is
an explicit, separate choice and is not replayed from history or a shared URL.
Database cursors and credentials are never serialized into the link. The recipe
labels this distinction when a database page is active.

## Inspect a small graph, then expand

The **Recorded sides** view starts with one provider side and up to five adjacent
names. Choose the focus, then expand to at most 12 or 18 displayed names. Counts
retain the full filtered-record basis and disclose the total available side labels
and how many focus-connected names are shown. An edge exists only where a provider
row records both side names. Neither co-recording nor layout establishes
membership, affiliation, influence, present authority or causation.

The **Context lenses** graph starts with at most 60 source records and can expand
to 250, 1,000 or 2,048. The full available count and keyboard/touch directory remain
available; expansion changes the drawing rather than the research query. When a
record is selected, the drawing prioritizes its existing field group and nearest
recorded dates. Otherwise it uses the first records in directory order. This is a
deterministic navigation aid, not a representative sample, semantic retrieval
ranking or measured saliency result. All five vocabulary alignments retain their
source qualifications.

## What the reproduction recipe guarantees

The recipe records the current shared view plus each dataset ID and SHA-256.
Links pin filters, not source bytes: compare these source identities when a host
refreshes its snapshot. No private text is copied into the recipe automatically.

Its runnable CLI command reproduces supported country/period/actor/category/
precision scope in ascending date and provider-ID order. Annual-series recipes use
the full retained year span, separately from event filters. The current CLI does
not implement browser record-text search, selected-event export or combined-series
selection. For those cases the recipe explicitly directs the reader to the shared
view or original exported JSON. It does not invent unsupported command flags or
claim byte-identical exports; timestamps, notes, ordering and size cutoffs can differ.

The `policy-research-selection/1` export contract and its 200-record/1 MiB bounds
remain unchanged. All 49 original UCDP attributes, dataset identities, source
locators and analyst/source distinctions still travel with each exported event.

## Verification

- `node --test tests/observations-navigation.test.mjs` checks URL round-trips,
  malformed/duplicate/oversized state, privacy exclusions, empty selected scope,
  deterministic graph subsets, source identities and shell-safe recipe quoting.
- `tests/observations-browser.js` extends the real-snapshot browser checks with
  Back/Forward, selected-event reload, invalid-filter notices, both starters and
  bounded graph expansion. It also checks original fields, export bounds,
  same-origin data access, mobile width and keyboard source inspection.
- The existing `test_observations.py` tests continue to validate source hydration,
  hashes, query counts and selection bounds.
