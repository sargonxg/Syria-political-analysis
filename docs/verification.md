# Verification: source atlas

Historical atlas-only checkpoint before the country/ontology merge and private-desk implementation. Current reconciliation and server checks are recorded in [desk verification](desk-verification.md); the current corpus contains 44 document references and 14 attributed paraphrases.

Checked locally on Windows with Python 3.12 and an isolated Chromium session on 2 November 2026. This is local verification, not a claim that remote CI or a deployment ran.

## Passed

- `python -m unittest discover -s tests -v`: 25 tests passed after catalogue integration. Coverage includes corpus/schema integrity, invalid/dangling relationship rejection, citation URL/date/evidence-ID validation, canonical homepage/name aliases, idempotent nondestructive merge, script-breakout data, safe output preservation and CLI builds.
- `syria-analysis validate`: 39 sources, 21 documents, nine claims, nine places, eight themes and two profile-linked social accounts. No social posts.
- `build-atlas`, `build-context`, JSON/GraphML exports and CSV exports completed after integration. Manifest and category counts match the corpus. Evidence graph: 86 nodes, 81 edges.
- `node --check src/syria_analysis/web/atlas.js`, Python compilation, Prettier checks and `git diff --check` passed.
- Isolated Python wheel build completed; all three HTML/CSS/JS package assets are included. An initial no-build-isolation attempt failed because the host lacks setuptools; the normal isolated build succeeded without installing into the system interpreter.
- 53 browser assertions passed after integration: the full 38-check interaction suite, 11 additional catalogue checks and four keyboard/reset checks. These cover all 47 research graph nodes, 17 relationships, all views, comparisons, filters, downloads, review qualifications, source aliases, historical publication dates, distinct operating-location lines, keyboard activation and retained focus, reduced motion and no browser JavaScript errors.
- All four views had no page-level horizontal overflow at 320, 768, 1024 and 1440 pixels. Small-screen graph scrolling is contained and has a directory alternative.
- Parsed downloaded JSON for zero-result, North Press, all-source and analyst filters contained exactly 0, 1, 39 and 4 selected profiles respectively, with no dangling relationship endpoints. Related institutional profiles are separate from the selected sources. The full download contains 17 relationships. Desktop light, dark and mobile layouts were visually inspected.
- Measured palette contrast on the paper surface: light text minimum 6.29:1, dark text minimum 7.65:1; relationship-line contrast 3.52:1 light and 4.67:1 dark. This is a token-level contrast check, not a full accessibility certification.

## Design gate

- Hard gate PASS: real corpus counts and original evidence links; every application control exercised; no invented findings; invalid data and empty states covered; keyboard graph activation, retained focus and qualification disclosures checked; responsive tests above.
- Purpose gate PASS: palette, typography, layout, constant-size nodes, restrained motion and selection styling have written reasons in `DESIGN.md`; no remote decorative assets or generic marketing claims.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; editorial headings, graph-plus-inspector focus and varied evidence/queue/worksheet structures were inspected in both themes.
- Craftsmanship PASS: 53 browser checks plus parsed export checks, formatting and builds passed; source text remains inert; no dead application controls; unknown relationship dates and source limitations remain available in profiles and their accessible review disclosures.

## Remaining boundaries

No remote deployment, GitHub push, merge, live collection or companion-website change was performed. Browser checks were run locally; no axe or screen-reader audit is claimed. Coverage is curated and incomplete, particularly dedicated coastal and Suwayda reporting.

The reviewed catalogue is committed as `data/sources/catalogue-review.json`. All 25 input profiles are represented: 11 additions and 14 supplements. Canonical ID/homepage/name resolution prevents duplicate outlets. Two overlapping relationships retain both evidence sets. Historical private input identifiers are optional archival metadata, not dependencies. Rebuild the portable atlas using the documented CLI and committed public citations.

GitHub main is not empty: its confirmed base commit is `29fa097cfe4077518a26b458ed8a534ed56f6dbd`. This local branch extends it; the metadata size-zero value was stale.

## Self-evaluation

Accuracy 4/5: dates, relationship semantics, counts and outputs are tested; profile descriptions remain attributed evidence rather than independent audits. Completeness 4/5: the catalogue is integrated and portable HTML delivered; coverage remains explicitly incomplete. Clarity 4/5: graph semantics and location lines are separated and caveats travel with records; dense graphs still benefit from the text directory. Actionability 4/5: the built HTML opens locally, a portable copy is saved and the CLI rebuild is documented; publishing remains a separate operation. Conciseness 4/5: the implementation has no runtime dependencies, though graph rendering and record presentation could eventually be split into additional modules. Overall 4.0/5.

Highest-impact follow-ups: fill dedicated coastal and Suwayda source gaps with evidence, review stale operating/language profiles, and undertake an external accessibility audit before broad public publication. These do not change the successful local checks above.
