# Political acts and a worked media comparison

This small collection shows how to preserve political information for analysis
without deriving it from organized-violence observations. It contains three
source-qualified records and one comparison of two reports about the same act.
It is a starter collection, not a comprehensive or live political-event feed.

## Run locally

From this checkout, Python 3.11+ is enough; the CLI adds its own source path and
needs no installed package, credential, network access, model or database:

```sh
python scripts/build_political_developments.py --output output/political-evidence
python scripts/build_political_developments.py --validate output/political-evidence/study.json
python scripts/build_political_developments.py --validate output/political-evidence/selection.json
```

The output directory contains `study.json`, `developments.json`,
`media-comparison.json` and `selection.json`. All four formats can be validated
against the trusted evidence in this checkout. Validation writes nothing.

Select only the documented Council act:

```sh
python scripts/build_political_developments.py \
  --ids sy-unsc-2254-adoption \
  --question "What act is documented, and what does it leave unestablished?" \
  --output output/council-act
```

The optional module API becomes available after `python -m pip install -e .` or
with `PYTHONPATH=src`. `build_study(root)` assembles the two committed data files;
`select_developments(study, ids, question)` exports complete selected records and
source metadata with their cited excerpts. `validate_selection(packet, study)`
checks the result against the local baseline and rejects altered evidence,
review state, dates or omissions rather than silently repairing them.

## Browse without the private personal website

The same collection has an independent, same-origin static browser study:

```sh
python scripts/build_political_developments.py \
  --output output/political-study/data \
  --html output/political-study/index.html
python -m http.server 8766 --bind 127.0.0.1 --directory output/political-study
```

Open `http://127.0.0.1:8766/`. Choose one of the three acts, inspect its date basis
and source excerpt, and download its prepared selection. The second view compares
the BBC and Guardian passages, separates observations from interpretation and
keeps the primary paragraph within reach. No private-site account is needed.

`build_browser(study, output_html_path)` writes one HTML file with adjacent
`political-study.js` and `political-study.css`. Python validates the study and
precomputes each one-record packet before rendering; the browser does not
reimplement evidence hashes, selection rules or provenance. Its embedded JSON
escapes HTML/script delimiters, and source material is rendered with `textContent`.
The CSP permits same-origin script/style assets and disables network connections.
There is no upload, API, account, local storage, analytics or model call. The
three static files can be copied to a static host or included in the existing
showcase. Browser assets are packaged in `src/syria_analysis/web/`, so both an
installed wheel and an editable checkout can build the viewer.

## What the three records establish

| Record | Act and event time | Source | Boundary |
| --- | --- | --- | --- |
| `sy-unsc-2254-adoption` | Council adoption, 18 December 2015 | Resolution 2254's primary adoption heading, printed page 1/4 | Adoption does not establish implementation of its negotiation, governance, election or ceasefire objectives. |
| `sy-envoy-council-briefing-2019` | Reported Council briefing, 30 September 2019 | UN News institutional report | The opening says “on Monday”; the dated article is Monday 30 September. This relative-date resolution is recorded explicitly. The retained source is reporting, not a verbatim meeting transcript. |
| `sy-homs-japan-unhabitat-announcement-2026` | Announced programme; no separately stated exact event day | UN Syria / UN-Habitat announcement, published 30 July 2026 | Event time stays null. July 2026–July 2028 is a source-reported plan, not a completion finding. |

A record's event time, publication/update dates and retrieval date have different
fields. Exact location is not manufactured; `coordinates` remains null. All
records retain pending human review, source attribution, qualifications and false
flags for established policy implementation/current conditions.

The new `political_development` kind is separate from `conflict_event`. The
existing historical dataset retains its original provider records and 49 fields.
No statistical association, co-occurrence, event-title keyword, source graph edge
or shared geography automatically becomes evidence of political causation,
representation, implementation or territorial control.

## The media comparison

The two real publisher pages concern the adoption of Resolution 2254:

- **BBC News**, “Syria war: UN Security Council unanimously backs peace plan”,
  first published **18 December 2015**, 19:31:04 UTC, modified 22:49:01 UTC.
  The page is a news report and contains a separate analysis inset attributed to
  Lyse Doucet. The retained text includes the headline, opening paragraph **and**
  its explicit acknowledgement of disagreement over Assad's future.
- **The Guardian**, Julian Borger, “UN resolution on Syria creates a framework –
  but one with yawning gaps”, **Analysis**, first published **19 December 2015**,
  13:32:59 UTC, with a recorded later modification in April 2018. A selected first
  paragraph illustrates how an analysis can compress several institutional terms.

The annotations distinguish observable text features from repository analyst
interpretations. For example, headline emphasis is compared without claiming
that the BBC report ignores disagreement; a retained counterexample shows that it
does not. The Guardian's language about government, a constitution and elections
can be checked against the primary paragraph 4, which is retained with its own
locator and attribution. The comparison does not convert a secondary paraphrase
into the instrument's verbatim wording.

Different genres and adjacent publication dates limit the comparison. Two
publishers do not establish independent corroboration: no complete reporting-
lineage audit was performed. No outlet-wide political orientation, bias,
credibility or trust score is assigned. These excerpts are not a representative
sample of either outlet's reporting.

## Provenance and rights

Political data: `data/political-developments/collection.json`.
Comparison: `data/media-comparison/2254-adoption.json`.

Each source keeps its official/publisher URL, original publication timestamp where
available, modification timestamp, retrieval day, capture digest and byte length.
Each excerpt has exact retained text, a locator and its own SHA-256. Only whitespace
was normalized. Capture hashes identify retrieved bytes; they do not certify truth,
independent reporting or a frozen publication-day edition.

The 2254 PDF fingerprint is
`932c9614e588e910c5c23a82b4df67679aba7bbe2c47ef2edd1d02970f0faa62`, matching the
previously retained official PDF. New adoption-heading text was checked against
that captured PDF. BBC, Guardian, UN News and UN Syria excerpts were compared to
retrieved publisher/official HTML on 7 November 2026. All checks were automated;
no completed human review is claimed.

Only short attributed excerpts and metadata are distributed. The full copyrighted
articles, publisher HTML, PDFs, images and unrelated page content are absent from
the repository and static build. Third-party source material retains its own
rights; the MIT code licence does not transfer those rights. Optional local
capture-fidelity tests use non-distributed research artifacts when present and
skip when those artifacts are absent in a clean checkout.

## Contracts and AI use

[`political_developments.schema.json`](../schemas/political_developments.schema.json)
defines four separately labelled formats:

- `political-evidence-study/1`: the combined worked collection and comparison.
- `political-developments/1`: the dated-act collection and its source book.
- `media-comparison-study/1`: the paired reporting and typed annotations.
- `political-development-selection/1`: an explicit bounded selection with cited
  excerpts, original qualifications, omitted IDs and a baseline fingerprint.

The Python validator adds date ordering, relative/unknown-date boundaries,
source/excerpt resolution, exact excerpt digests, source-selection fidelity and
512 KiB/depth/value limits. It rejects duplicate keys, private literal IP references,
embedded URL credentials, promoted implementation/review flags, causal conflict
links and unsupported publisher-score fields. A successful schema check is not
verification of a political conclusion.

Provide a selection as lower-trust evidence to an AI system, keeping the research
question and system instructions separate. Ask for citations by record and excerpt
ID, distinguish the documented act from its objectives, retain unknown dates and
follow-up evidence needs, and verify consequential conclusions against the source.
Source text is data, never instructions to execute or obey. This toolkit calls no
model and claims no measured answer-quality, relevance, token or cost gain.

The separately maintained personal site consumes `study.json` through the compact
`PoliticalEvidenceStudy` component. Its selected-record downloads were validated
against the Python contract. These formats are not native TACITUS/PRAXIS contexts
or verified attachments to a paused workspace.
