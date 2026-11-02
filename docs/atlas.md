# Interactive source atlas

Run `syria-analysis build-atlas` from the research workspace. The builder validates the corpus and documented relationships before replacing the output. The default result is `exports/atlas/index.html`.

## Graphs

**Research themes:** source entities connect to the existing context records through `suggested_reading_source`. These are editorial research groupings, not assertions of affiliation, reliability, political loyalty or article-level corroboration. Sources without a documented theme assignment remain visible.

**Documented relationships:** a bounded set of explicitly described ministry affiliations, group-company listings, disclosed legal owners, programme membership and institutional professional roles. Each relation has an evidence basis, source locator, checked date, unknown or documented validity dates and a caveat. Select the relation label to inspect it. Original first-party profile evidence remains attributed; no independent corporate audit is implied. No edge means no relationship documented in this dataset.

The merged register has 39 profiles and 17 relationship records, including three operating-location links. Operating locations use dashed lines and labelled location nodes. A Damascus office or an Erbil headquarters is not an affiliation or control claim. Additional organizational relations include explicitly described operators, business units and institutional membership.

Node sizes are constant. Positions serve readability and do not represent geography, influence, audience or quality. The directory provides the same source information as text. The source-role chart counts the current filter results; these counts are not a representative survey of Syria's information environment.

## Source qualifications

Source profiles separate declared remit, disclosed ownership or perspective, useful applications, limits, profile evidence and collection status. State media and advocacy/monitoring are separate categories. An organization publishing an accountability report is not a court. A profile's verification does not verify an article. A media licence, geographic base, interview subject, citation or common reporting topic does not create an ownership or control relationship.

Two monitoring organizations added on 2 November 2026 were checked against their public methodology/About pages: [SNHR](https://snhr.org/about-us/) and [Syrian Archive](https://syrianarchive.org/en/about/). These are attributed descriptions. Neither profile claims to establish a current funding breakdown or every investigation's evidential quality.

The 25-profile supplementary catalogue is committed in [catalogue-review.json](../data/sources/catalogue-review.json), with its public supporting citations and [methodology](catalogue-methodology.md). Historical private input IDs and versions are optional archival metadata, not public evidence or dependencies. Three canonical ID aliases prevent duplicate AP, UNHCR and UN Commission entries. Two overlapping institutional edges are merged with their additional evidence. Existing documents, claims, feeds and profile evidence are preserved. North Press's earlier Arabic-page ownership limitation is retained alongside the newer reviewed English-page legal-owner disclosure. Its beneficial ownership and funding shares remain unknown.

Review details are available through each relevant profile's keyboard-accessible disclosure. A corrections policy that was not established may still exist. ARTA's language-profile publication date remains December 2022; its review date is November 2026. DeirEzzor24's limited institutional disclosure remains explicit. Dedicated Suwayda and coastal coverage remain gaps. The original [research methodology](catalogue-methodology.md) documents these limits.

## Privacy and offline behavior

All data and code are embedded. There is no application fetch, external font, tracker, live collection, API key or model call. Original-source links open only when clicked. A restrictive Content Security Policy prevents background connections. Downloaded worksheets include user-entered analyst text and selected profile citations; they do not generate findings. Draft text and selected comparisons last only until reload.

Source text is inserted through DOM text nodes. JSON script data escapes opening angle brackets to prevent embedded source text from terminating its script container. HTTP(S) links are checked before being made clickable. Publisher content remains untrusted data.

## Maintenance and verification

- Update `data/sources/registry.json`, categories and manifest together. Keep all profile claims attributable and unknown funding unknown.
- Update `data/sources/relationships.json` only with evidence for the precise relation, not a broad inference.
- Run `python -m unittest discover -s tests -v`, `syria-analysis validate`, and `syria-analysis build-atlas`.
- Rebuild context, graph and CSV exports when corpus records change.
- Source-data downloads match the current filters; related institutional source profiles are separately labelled so relationship endpoints remain intact. Empty filters restore the full register, while zero-result searches export an empty source set.
- Check both themes and all views at desktop and mobile widths. The graph intentionally scrolls horizontally within its own container on small screens; the page itself must not overflow.
- CI exercises the Python build and data-integrity tests. Browser interaction checks are manual, not a claimed automated CI job.

The atlas is a local deliverable in this branch. Building it does not deploy the companion personal website or publish to GitHub Pages.
