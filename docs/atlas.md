# Interactive source atlas

Run `syria-analysis build-atlas` from the research workspace. The builder validates the corpus and documented relationships before replacing the output. The default result is `exports/atlas/index.html`.

## Graphs

**Research themes:** source entities connect to the existing context records through `suggested_reading_source`. These are editorial research groupings, not assertions of affiliation, reliability, political loyalty or article-level corroboration. Sources without a documented theme assignment remain visible.

**Documented relationships:** a bounded set of explicitly described ministry affiliations, group-company listings, disclosed legal owners, programme membership and institutional professional roles. Each relation has an evidence basis, source locator, checked date, unknown or documented validity dates and a caveat. Select the relation label to inspect it. Original first-party profile evidence remains attributed; no independent corporate audit is implied. No edge means no relationship documented in this dataset.

Node sizes are constant. Positions serve readability and do not represent geography, influence, audience or quality. The directory provides the same source information as text. The source-role chart counts the current filter results; these counts are not a representative survey of Syria's information environment.

## Source qualifications

Source profiles separate declared remit, disclosed ownership or perspective, useful applications, limits, profile evidence and collection status. State media and advocacy/monitoring are separate categories. An organization publishing an accountability report is not a court. A profile's verification does not verify an article. A media licence, geographic base, interview subject, citation or common reporting topic does not create an ownership or control relationship.

Two monitoring organizations added on 2 November 2026 were checked against their public methodology/About pages: [SNHR](https://snhr.org/about-us/) and [Syrian Archive](https://syrianarchive.org/en/about/). These are attributed descriptions. Neither profile claims to establish a current funding breakdown or every investigation's evidential quality.

## Privacy and offline behavior

All data and code are embedded. There is no application fetch, external font, tracker, live collection, API key or model call. Original-source links open only when clicked. A restrictive Content Security Policy prevents background connections. Downloaded worksheets include user-entered analyst text and selected profile citations; they do not generate findings. Draft text and selected comparisons last only until reload.

Source text is inserted through DOM text nodes. JSON script data escapes opening angle brackets to prevent embedded source text from terminating its script container. HTTP(S) links are checked before being made clickable. Publisher content remains untrusted data.

## Maintenance and verification

- Update `data/sources/registry.json`, categories and manifest together. Keep all profile claims attributable and unknown funding unknown.
- Update `data/sources/relationships.json` only with evidence for the precise relation, not a broad inference.
- Run `python -m unittest discover -s tests -v`, `syria-analysis validate`, and `syria-analysis build-atlas`.
- Rebuild context, graph and CSV exports when corpus records change.
- Check both themes and all views at desktop and mobile widths. The graph intentionally scrolls horizontally within its own container on small screens; the page itself must not overflow.
- CI exercises the Python build and data-integrity tests. Browser interaction checks are manual, not a claimed automated CI job.

The atlas is a local deliverable in this branch. Building it does not deploy the companion personal website or publish to GitHub Pages.
