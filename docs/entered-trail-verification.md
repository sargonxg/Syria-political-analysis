# Entered evidence trail — 0.3.1

Verified 5 November 2026. This change adds a browser-derived view to **Assess framing**. It does not collect sources, fetch reports, infer affiliations or change `media-framing-assessment/1`.

## Behavior checked

The diagram has three relationship types: selected publisher attribution, entered report passages, and named upstream reference. A blank worksheet has no report relationships. Publisher changes clear only that report's fields and trail. Selecting a quotation shows its exact entered text, line breaks, locator and separately labelled analyst note. HTML-like quotation text remains inert text.

Repeated upstream URLs converge only after the existing normalization removes fragments and common tracking parameters. Distinct paths on one host remain distinct. Unsafe/empty URLs produce no reference node or edge. Original URL forms remain in the inspector and export. A shared reference does not establish independent corroboration.

Interpretation, alternative explanations and missing evidence stay in an unreviewed analyst node. No support edge is assigned to it: the current contract contains no claim-level evidence-support record. A report-level upstream URL is not assigned to each quotation. The text connection list carries the same entered relationships as the diagram.

## Results

- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`: **67 tests passed**. The sandbox run used network permission for the private desk's in-memory TestClient. An earlier run without that permission stalled and was stopped; no desk implementation change was needed.
- Corpus validation: **55 source profiles, 44 document references, 14 paraphrases, 14 navigation anchors, eight context themes and eight analytical lenses**. Seven political entities, six qualified assertion drafts and 18 concepts validate.
- `tests/media-browser.js`: **50 assertions passed** at 1440px and 390px, with no uncaught errors, page overflow or external requests. Checks cover keyboard selection, shared/distinct/unsafe references, exact/inert quotation text, stale-selection clearing, publisher changes and unchanged export provenance, including the existing asynchronous-hash race test.
- The downloaded browser JSON validates against `schemas/media_assessment.schema.json`.
- Axe WCAG 2 A/AA and WCAG 2.1 AA checks on the comparison view: **zero violations and zero incomplete checks**, in light/dark themes at both widths. This is scoped automated evidence, not a complete accessibility certification.
- Python lint/format checks, JavaScript syntax and Prettier checks pass. `git diff --check` passes.
- The static build and regenerated standalone atlas pass the required editorial-name scan. Source profiles, document/claim records, source relationships, saved reading sample and collection timestamps were not changed.

## Reproduce

Install the repository's documented development/test dependencies, then run:

```sh
python -m unittest discover -s tests -v
python -m syria_analysis validate
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Run the existing browser test through the [CI browser workflow](../.github/workflows/ci.yml). Its `testMedia(page)` defaults to loopback port 8766 and accepts an alternative base URL for isolated local runners. The verification used installed Playwright, system Chromium and Axe; no hosted service or deployment was tested.

The toolkit version is aligned at **0.3.1** in package metadata, `__version__` and the data manifest. The standalone atlas export is regenerated from the same source assets. The view is not exported as a new graph contract; entered records remain authoritative.

## Limits

Reports, passages, locators, source attribution and upstream links are entered by the researcher. The app does not authenticate them or check quoted text against an article. The view groups quotation slots for inspection; it is not an assertion that they are separate independent evidence items. Worksheet state still lives only in the open tab until an explicit download. On narrow screens the diagram scrolls horizontally, with keyboard-selectable records and a text alternative.
