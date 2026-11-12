# Syria-political-analysis · purpose and practical use

Query historical provider records, inspect source fields and export a bounded research selection without inventing a political conclusion.

**Role:** Local public-source toolkit.

**Current boundary:** Historical datasets, curated source profiles and private notebooks have separate coverage and access requirements. Records are not a current event feed.

## Start with one useful workflow

Python 3.11+; committed datasets are separate from live collection.

```sh
python -m pip install -e ".[dev,desk,test]"
python -m unittest discover -s tests -v
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

These application commands are separate from the teaching demo below. Check the recorded results before treating a command as verified. A successful bundle build does not establish provider availability, authenticated ownership or a working hosted deployment.

## How the code fits together

| Entry point | What to inspect |
| --- | --- |
| [scripts/build_showcase.py](scripts/build_showcase.py) | Builds the static public research atlas from committed snapshots, independently of the private notebook server. |
| [src/syria_analysis](src/syria_analysis) | Implementation/data directory for this workflow. Follow the declared types and source identifiers through the relevant route, compiler or view before adapting it. |
| [schemas/research_selection.schema.json](schemas/research_selection.schema.json) | Describes the bounded research handoff. This format is separate from native capsules. |

## Its place in TACITUS

The common goal is reusable, reviewable policy context: sources → explicit structure → task context → draft/artifact → human review. This repository contributes the role described above. Existing schemas, identity systems and review receipts remain authoritative within each implementation. A similar name such as “graph”, “context” or “capsule” does not establish binary or semantic compatibility.

For a downstream adapter, first pin a source/version and rights notice, state the task and output schema, retain attribution and time qualifications, then test export/re-import and refusal cases against the actual destination. No adapter is represented as working merely because the two projects appear in this portfolio.

## Play the idea before running the stack

[The House of Evidence](tacitus-demo/index.html) is an original four-room point-and-click adventure. Preserve a conditional promise, attribute a claim, inspect its chronology and download a brief with the uncertainty intact. It is a synthetic teaching fixture, not a run of this repository’s engine.

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory tacitus-demo
```

Open `http://127.0.0.1:8765/`. The directory is also a standalone static artifact: copy its contents to a static host to publish only the adventure. No model, credential, database or package installation is needed. Opening `tacitus-demo/index.html` directly works in browsers that allow local files.

The shared teaching engine passed desktop (1440×1080) and mobile (390×844) Chromium checks for wrong answers, incomplete-review refusal, exact quotation export, separate notes, reset and horizontal overflow. [Fixture receipt](tacitus-demo/browser-verification.json). This verifies the shared demo, not the application.

## Research, credit and the contribution to evaluate

[Lewis et al., RAG (2020)](https://arxiv.org/abs/2005.11401), [Liu et al., Lost in the Middle (2023)](https://arxiv.org/abs/2307.03172), and [Edge et al., GraphRAG (2024; revised 2025)](https://arxiv.org/abs/2404.16130) motivate separating retrieval, context use and global synthesis. Read the [methods, evaluation limits and TACITUS design notes](https://github.com/sargonxg/sargonxg/blob/main/docs/RESEARCH_AND_DESIGN.md). Their results are not measurements of this repository.

Retain existing licenses and notices for application dependencies and bundled sources. The new adventure code, synthetic dispatches and generated mansion artwork are credited in [tacitus-demo/CREDITS.md](tacitus-demo/CREDITS.md). The demonstration does not relicense this repository or its external source documents.

The practical improvement to test is whether this workflow reduces a specific failure or repeated task: lost attribution, omitted conditions, stale evidence, untraceable drafting or repeated source preparation. Measure that against a matched baseline with source review, complete costs and held-out tasks before claiming analytical or efficiency gains.

## Verification in this pass

Audited default-branch baseline: `4d7c6ec55c1a1435cd7449b6e02d5640205f0d89`. Changes were prepared from a fresh shallow checkout. The audit covers this branch, not every historical or in-progress branch.

| Command | Local result |
| --- | --- |
| `python -m unittest discover -s tests -v` | Passed |

A failure is a remaining release blocker for the affected workflow. A passing local test is not a new hosted release. Provider/model quality, current external-service setup and production deployment were not certified.

## Reconciliation checkpoint · 11 November 2026

203 Python tests pass, 145 subtests pass, two service-dependent tests skip. The default branch now includes the document-knowledge case and query resilience work. Historical datasets remain dated; no live intelligence or analytical-quality claim follows from these checks.
