# A complete source, a qualified graph, a bounded handoff

This local case follows a real AI-policy document from its captured publication
through searchable storage, typed assertions and task-specific context. It uses
**Executive Order 14179**, signed 23 January and published 31 January 2025.
It is a historical document study, not a determination of current law.

The three useful operations are: inspect what the instrument says, preserve the
conditions behind a proposed brief, and reopen the same source/graph locally.
Everything below runs without a model account, cloud service or database server.

## Run it

Python 3.11+ with the standard SQLite FTS5 extension is sufficient. From the
repository's `codex/policy-document-knowledge-20261107` branch:

```sh
python scripts/build_policy_case.py --output output/policy-case
python -m http.server 8768 --bind 127.0.0.1 --directory output/policy-case
```

Open **http://127.0.0.1:8768/**. Choose one of four questions, follow a graph
link to the actual assertion, open its source passages, and download the complete
context or draft prompt. The full captured text and a source receipt are available
alongside the graph. A new output directory is required on each build; earlier
work is preserved.

Search and prepare context from the saved database:

```sh
python scripts/build_policy_case.py --database output/policy-case/research.sqlite3 --search "availability appropriations"
python scripts/build_policy_case.py --database output/policy-case/research.sqlite3 --task action-plan --max-bytes 16000
```

The first command returns the exact section 6(b) passage. The second reopens the
source and model read-only, selects the action-plan claim with its declared
qualifications, and returns the prompt and its exact UTF-8 byte count. If the
complete prompt does not fit, it refuses; it does not cut a qualification to fit.

## What is captured and what is interpreted

| Layer | Retained data | How to inspect it |
| --- | --- | --- |
| Original publication response | 7,060 bytes, including Federal Register front matter, page markers and extraction artifacts | `data/policy-case/eo-14179/source.html`, SHA-256 in receipt |
| Normalized complete order | 4,281 UTF-8 bytes: title, all six sections, general provisions and signature/date | `document.txt`; normalization is reproducible from the raw capture |
| Mechanical segmentation | All 17 nonempty text blocks, exact normalized-text byte spans and hashes | SQLite `paragraph` and `paragraph_search` |
| Draft semantic model | 15 typed entities and eight source-linked assertions | `model.json`; SQLite `entity`, `assertion`, `evidence` |
| Context requirements | Explicit dependencies connecting instructions to qualifications | SQLite `dependency`; each claim's `requires` |
| Research task | Explicit seeds, their dependency closure, retained evidence and omitted IDs | `contexts/*.json`, complete `*.txt` prompt and `evaluation.json` |

The raw-text endpoint actually returns an HTML PRE wrapper with NUL artifacts.
The original response stays byte-for-byte intact. The narrow example normalizer
extracts that PRE text, selects EO14179 rather than adjacent front matter,
removes page/NUL artifacts and reflows whitespace. Citation offsets refer to
**the normalized text**, not the raw HTML or PDF. The builder checks both hashes
and regenerates normalized text before storing it.

All text is captured; **complete semantic extraction is not claimed**. Titles,
publication furniture and unannotated content remain searchable. The eight
assertions are supplied editorial drafts. Source verbs are checked against the
cited paragraphs, but that check does not establish that the paraphrase is correct
or that every actor, condition and meaning has been modeled. No human review,
legal opinion or implementation evidence is invented.

The source is an official US presidential document published by the Office of the
Federal Register/National Archives. The receipt records attribution and the
17 U.S.C. 105 basis for the federal-government text. That basis does not apply
automatically to other documents a user imports.

## Ontology and graph semantics

This case reuses classes in [`ontology/core.json`](../ontology/core.json):
`LegalInstrument`, `PublicActor`, `InstitutionOrOrganization`,
`NormativeObjective`, `PoliticalProcess`, `Concept` and `Assertion`.
Relations such as `directs`, `conditions_on` and `preserves_authority` are an
explicit **document-case extension**, not a silent alteration of the Syria
country ontology or a claim of comprehensive legal-ontology compliance.

One draft assertion records the issuing office, the named addressed roles,
`shall develop and submit`, the action-plan objective, exact evidence blocks,
relative time wording and the legal/funding qualifications. The graph retains
the difference between a direction, an attributed report and an analyst view.
Every example assertion remains `needs_source_check`, with no human review or
implemented outcome established.

`graph.jsonld` has an inline context and uses **RDF statement reification**.
The source-scoped assertion holds `rdf:subject`, `rdf:predicate`, `rdf:object`,
the exact source verb, addressed actors, qualifications, required records and
review flags. PROV-O `wasDerivedFrom` links it to paragraph evidence and the
source. It does **not** emit a bare political triple asserting that a directed
action occurred. Reification also does not prove truth or legal effect.

The namespaces are `urn:policy-analysis:ontology:core:` for shared classes and
`urn:policy-analysis:document-case:` for this extension. This is not the native
TACITUS/PRAXIS capsule contract, a historical event selection or an automatic
interchange adapter. Other native capsule formats remain separate.

## Why the context is useful to an AI workflow

For “who must prepare the action plan?”, a seed-only selection retains section 4
and loses the declared policy, statutory-authority and appropriations context.
The dependency-closed selection keeps those records and their exact passages.
A brief can then say what the instrument **directs**, who is addressed and what
still needs evidence. It should not claim that an action plan was delivered just
because the instrument contains a 180-day instruction.

An **authored example of supported wording**, not a recorded model response:

> The January 2025 order directs APST, the Special Advisor for AI and Crypto,
> and APNSA, with the listed coordinating officials, to develop and submit an
> action plan within 180 days [p007]. It states a policy objective [p005],
> preserves existing authority and OMB functions [p010–p012], and makes
> implementation subject to applicable law and appropriations [p013]. These
> passages do not establish that the plan was submitted or funded.

The deterministic comparison for this task is:

| Input | Complete prompt UTF-8 bytes | Declared required records missing |
| --- | ---: | --- |
| All eight structured assertions | 13,535 | 0 |
| Selected instruction plus declared dependencies | 7,498 | 0 |
| Seed instruction only, deliberately incomplete comparison | 3,679 | 3 |
| Original normalized document, without the graph prompt | 4,281 | Not evaluated by this annotation rubric |

These are two different baselines. Selection is smaller than the full structured
prompt; the structured prompt is larger than this short source. Omitting context
can reduce bytes while damaging a brief. No token, latency, API cost, generation
quality or independently judged saliency improvement has been measured.
The rubric is implementation-authored dependency coverage, not political ground
truth or external relevance review.

To test generation, use the same model/version and question across original-text,
full-graph and selected-context prompts. Record the actual provider token counts,
latency and outputs, and have an independent reviewer assess source entailment,
qualification retention, implementation overclaims and omitted evidence. Report
failed cases and total ingestion/review cost. This repository supplies the inputs
and comparison records; it does not fabricate that experiment.

## Store your own document

The generic module API accepts bounded UTF-8 text, explicit source metadata and a
supplied model. Start from the example model, revise its entities/assertions/tasks,
and keep source IDs, exact evidence references and draft-review boundaries.
A case directory contains `document.txt`, `model.json`, and `receipt.json` with
`title`, `uri`, `published_on` and `normalized_sha256`. Optional capture, rights and
signature-date fields describe the source; they do not establish authenticity.
The specialized Federal Register normalizer runs only for the bundled document ID.

```python
from pathlib import Path
from syria_analysis.document_knowledge import read_json, reopen, select_context, write_database

text = Path("my-case/document.txt").read_text(encoding="utf-8")
model = read_json("my-case/model.json")
source = {"title": "My supplied policy document", "uri": None, "published_on": None}
write_database(Path("new-research.sqlite3"), text, source, model)
text, source, model = reopen("new-research.sqlite3")
context = select_context(text, source, model, model["tasks"][0]["id"], max_bytes=16000)
```

`python scripts/build_policy_case.py --case my-case --output output/my-new-case`
adds the standalone viewer and exports. Set a valid HTTP(S) `uri` if the viewer
should offer an original-publication link. No URL is fetched during a build.

Bounds: 128 KiB of text, 128 text blocks, 128 entities/assertions/tasks, eight
paragraph references and 16 addressed actors per assertion, 1,024 dependency
edges, 256 KiB model JSON and 256 KiB maximum prompt. Search uses an FTS index,
parameterized terms and an explicit 1–50 result limit. Reopen checks the stored
source/model digests and each relational projection against the supplied model;
checks prove internal consistency, not author identity. SQLite is local plaintext,
not encryption or a multi-user access-control service. Export directories/files
are owner-only on POSIX and are never overwritten.

The viewer escapes supplied text, uses hashed inline code/styles and blocks
runtime network connections through its CSP. Its graph links have keyboard-accessible
HTML evidence equivalents. A normal no-JavaScript view shows every task and source
passage. Source instructions are reference data, never executable code or a grant
of model tool permissions. Downstream model applications must enforce that boundary.
