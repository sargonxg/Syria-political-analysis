# Historical atlas verification · 5 November 2026

This check covers the committed historical event snapshot, annual-country connector, browser atlas, bounded research-selection contract and documented local workflows. It does not establish independent source accuracy, causal effects or current territorial conditions.

## Source and data checks

- UCDP GED Global 26.1: the official archive and CSV identities match their pinned byte sizes and SHA-256 receipts. The selected 2011–2025 collection contains 113,656 unique retained records in nine provider country categories. All 49 original string-valued fields are preserved and checked against each record's canonical digest. Every compact point joins exactly to its raw partner.
- There are 228 compact partitions and 228 full-record partners. The largest event file is 1,572,830 bytes, below the 1.5 MiB partition limit. The default Syria 2020–2025 view loads 5,263 compact events in 4,264,217 bytes; full source fields remain lazy.
- Source low/best/high estimates remain unchanged. There are 664 nonordered estimate triples: 93 with clarity code 2 and 571 with clarity code 1. The codebook's aggregate-subtraction explanation can apply to some cases; it is not asserted as the explanation for every nonordered triple.
- World Bank: 15,272 non-null annual values, 5,848 returned null rows recorded separately, 24 genuine zeros, 32 explicitly licensed annual WDI series and ten economies. Forty-two archived API responses, per-series metadata, raw units/statuses, receipt hashes and missingness are retained. Nineteen served country partitions remain below 1.5 MiB.
- Served text/data were screened against publication-scope exclusions; retained source fields were not rewritten. Global archives and the original source-codebook PDF are not copied into the static site.

## Executed checks

The project environment's complete Python suite passed **108 tests**, including every-record snapshot integrity, deterministic sharding, missingness/licence boundaries, unsafe paths, altered files, raw joins, bounded exports and the shared cross-language contract cases. Ruff checks and formatting pass for the new Python modules/scripts/tests. The production static build and JavaScript syntax checks pass.

The maintained `tests/observations-browser.js` passed **19 checks** against actual data at 1440 and 390 pixels: default record counts, pagination, 49-field inspection, category/precision filters, bounded full-record exports, annual-only exports, recorded-side relationships, rapid country switching, keyboard/touch alternatives and absence of external API requests or page errors.

Five deliberate response-tamper scenarios passed: altered compact bytes, false compact row count, altered annual data, altered raw bytes, and altered original fields with the raw-file manifest checksum updated. The browser blocks display/export as appropriate; a failed parallel load remains a visible terminal error until retry.

Ten selected-state desktop/mobile Axe scans reported **zero violations**, zero document overflow and zero page errors. Color-contrast checks for the zoom-minus glyph and partially clipped mobile table cells remained automated incomplete results. This is scoped automated testing, not a complete accessibility certification.

A separate full-volume browser smoke test explicitly opened all **88,279 Syria points**, with 15 directory rows in the DOM, working pan/zoom/fit, no page errors and no application animation-frame calls during a one-second idle sample. Its roughly 2.7-second local load is an environment-specific functional observation, not a production or mobile performance guarantee.

## Interchange and practical examples

The Python and TypeScript readers agree on the shared synthetic semantic fixtures and UTF-8/BOM/CRLF byte boundaries. Actual source-kit exports—including 200 full UCDP records and 66 annual population values—opened in Workbench at desktop/mobile widths and re-exported byte-for-byte. Native Context mode and its original export remained separate.

The [committed event example](../examples/historical-research/syria-events.json) contains 12 of 323 matching Syria 2024–2025 records, with explicit truncation. The [GDP example](../examples/historical-research/syria-country-context.json) contains 12 available 2011–2022 values, despite requesting through 2025. Both pass `policy-analysis validate-selection`.

No native Rust build, model-answer evaluation, public hosted API or PRAXIS service operation is certified by this pass. Static assets and the optional authenticated private notebook remain different deployment workflows.
