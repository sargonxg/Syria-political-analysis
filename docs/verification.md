# Verification: source atlas

Checked locally on Windows with Python 3.12 and an isolated Chromium session on 2 November 2026. This is local verification, not a claim that remote CI or a deployment ran.

## Passed

- `python -m unittest discover -s tests -v`: 19 tests passed. Coverage includes corpus/schema integrity, invalid/dangling relationship rejection, script-breakout data, safe output preservation and CLI builds.
- `syria-analysis validate`: 28 sources, 21 documents, nine claims, nine places, eight themes and two profile-linked social accounts. No social posts.
- `build-atlas`, `build-context`, JSON/GraphML exports and CSV exports completed. Manifest and category counts match the corpus. Evidence graph: 75 nodes, 81 edges.
- `node --check src/syria_analysis/web/atlas.js`, Python compilation, Prettier checks and `git diff --check` passed.
- Isolated Python wheel build completed; all three HTML/CSS/JS package assets are included. An initial no-build-isolation attempt failed because the host lacks setuptools; the normal isolated build succeeded without installing into the system interpreter.
- 38 browser assertions passed: all 36 research graph nodes; six relationship records and their evidence; combined filters; empty state; directory; all four views; comparison limit and removal; required-question feedback; Markdown and JSON downloads; theme toggle; reduced motion; and no browser JavaScript errors.
- All four views had no page-level horizontal overflow at 320, 768, 1024 and 1440 pixels. Small-screen graph scrolling is contained and has a directory alternative.
- Final JSON download contained 28 profiles and six relationships. Desktop light, dark and mobile layouts were visually inspected.
- Measured palette contrast on the paper surface: light text minimum 6.29:1, dark text minimum 7.65:1; relationship-line contrast 3.52:1 light and 4.67:1 dark. This is a token-level contrast check, not a full accessibility certification.

## Design gate

- Hard gate PASS: real corpus counts and original evidence links; every application control exercised; no invented findings; invalid data and empty states covered; keyboard graph activation and focus styling checked; responsive tests above.
- Purpose gate PASS: palette, typography, layout, constant-size nodes, restrained motion and selection styling have written reasons in `DESIGN.md`; no remote decorative assets or generic marketing claims.
- Liveliness PASS: ENERGY 1 / RHYTHM 2 / MOTION 1; editorial headings, graph-plus-inspector focus and varied evidence/queue/worksheet structures were inspected in both themes.
- Craftsmanship PASS: 38 browser checks, formatting and builds passed; source text remains inert; no dead application controls; unknown relationship dates and source limitations remain visible.

## Remaining boundaries

No remote deployment, GitHub push, merge, live collection or companion-website change was performed. Browser checks were run locally; no axe or screen-reader audit is claimed. Coverage is curated and incomplete, particularly dedicated coastal and Suwayda reporting.

A separately supplied research catalogue could not be materialized using its required Library helper on Windows: `os.setxattr` is unavailable. Its bytes were not installed into the repository, and its larger catalogue is not represented as integrated. The atlas uses the existing checked corpus, the six relationships documented from its profile evidence, and two additional profiles checked directly against their original public About/methodology pages.

## Self-evaluation

Accuracy 4/5: dates, relationship semantics, counts and outputs are tested; profile descriptions remain first-party evidence rather than independent audits. Completeness 3/5: the functioning atlas is delivered, but the separately supplied catalogue import remains blocked and coverage is not exhaustive. Clarity 4/5: the two graph semantics are separated and caveats travel with records; dense graphs still benefit from the text directory. Actionability 4/5: the built HTML opens locally and the CLI rebuild is documented; publishing remains a separate operation. Conciseness 4/5: the implementation has no runtime dependencies, though graph rendering and record presentation could eventually be split into additional modules. Overall 3.8/5.

Highest-impact follow-ups: resolve the supported catalogue transfer on a compatible host; then review and merge its nonduplicate profiles with provenance; undertake an external accessibility audit before broad public publication. These do not change the successful local checks above.
