# A policy document, made inspectable

This offline worked example helps a reader answer a narrow question: **what did
Security Council resolution 2254 (2015) request or support, and what would establish
implementation?** Choose negotiations, institutions or ceasefire, inspect the
retained primary excerpt and its qualified editorial assertions, then export the
selected evidence with explicit omissions and follow-up questions.

It does not produce an AI answer. The question labels an explicit selection; no
model, embedding, semantic search, live feed or ranking service runs. Everything is
Python standard library code, with public curated JSON as input and no database,
Cloudflare, private case, credential or network access.

## Build and try it

From a checkout with Python 3.11 or later, no installation is needed:

```sh
python scripts/build_policy_document.py
python scripts/build_policy_document.py --task institutions --output output/policy-institutions
python scripts/build_policy_document.py --task negotiations --select norm-2254-op2-convening norm-2254-op5-ceasefire --question "What connects the request for negotiations with the ceasefire objective?" --output output/policy-comparison
python scripts/build_policy_document.py --validate output/policy-document-20261107/selection.json
```

The default directory contains `lab.json`, a site-friendly bundle with six complete
canonical assertion records, three primary excerpts, record-specific evidence gaps
and three predefined tasks; `selection.json`, the requested task/subset; and
`negotiations.json`, `institutions.json` and `ceasefire.json`, their default packets.
Builds are deterministic for identical input and arguments. A supplied question
changes the label, not the selected evidence. Visitor selections retain one to six
distinct known record IDs, normalized to source-record order. Unknown/duplicate IDs,
blank or oversized questions and malformed input are rejected rather than repaired.
Validation writes nothing and checks against the local curated baseline.

The independent module API is:

```python
from pathlib import Path
from syria_analysis.policy_document import build_selection, load_corpus, validate_selection

corpus = load_corpus(Path("."))
packet = build_selection(*corpus, "negotiations")
assert validate_selection(packet, *corpus)
```

## Evidence and provenance

The unchanged receipt is `doc-83ad8cbb868c0c88` in
[`data/documents/receipts.json`](../data/documents/receipts.json). The resolution was
adopted on **18 December 2015**. Its six dated normative assertion drafts in
[`data/ontology/assertions.json`](../data/ontology/assertions.json) retain their
original IDs, complete evidence references, source verbs, dates, conditions,
qualifications and review state. They are **editorial paraphrases**, not quotations.
All remain `needs_source_check`, with `human_review_recorded: false` and
`implementation_asserted: false`. This workflow never changes those records.

[`data/policy-document/2254-passages.json`](../data/policy-document/2254-passages.json)
separately retains **selected primary excerpts** from operative paragraphs 2 and 4
(printed page 2/4) and paragraph 5 (printed page 3/4). They were captured on
**7 November 2026** from the [official PDF](https://documents.un.org/doc/undoc/gen/n15/443/34/pdf/n1544334.pdf),
using `pdftotext -layout`, and normalized only for whitespace. Paragraph numbers are
retained; page furniture is outside the selected excerpt. The PDF is 234,927 bytes
with SHA-256
`932c9614e588e910c5c23a82b4df67679aba7bbe2c47ef2edd1d02970f0faa62`, matching the
digest previously recorded in the receipt. The capture records an automated check,
**not completed human review**. The original receipt remains unchanged and still
correctly does not claim a retained full-text collection.

These three excerpts are not the whole resolution. Paragraph 4 supports four
qualified assertions, making the passage-to-several-objectives relationship
inspectable. Selecting one of those assertions retains the complete paragraph 4
excerpt: other objectives inside that passage are not silently edited away.
Paragraph 5 is not the whole ceasefire framework; paragraph 8 and the complete
instrument are necessary to assess its scope and exclusions.

## Political developments and conflict observations

A request to convene negotiations is not proof that talks occurred or that a named
participant holds a current mandate. Support for inclusive governance, constitutional
drafting or elections does not establish an implemented arrangement, adopted
constitution or election date. A condition-linked ceasefire objective does not
establish an agreement in force, territorial control or compliance. The original
2015 target language is retained without manufacturing current deadlines.

Political acts and developments require their own attributed records. They are
distinct from organized-violence observations such as UCDP event records. A document
adoption, programme announcement, invitation, actual meeting and implemented outcome
are also different developments. A political document's publication date is not
silently used as an event date, and proximity in time, place or topic does not prove
causation. The six national normative objectives remain unpinned (`coordinates:
null`); this example does not invent meeting coordinates or control boundaries.

## Separate selection contract

The packet is **`policy-document-selection/1`**, with its standalone
[`JSON Schema`](../schemas/policy_document_selection.schema.json). It is not
`policy-research-selection/1` (whose record kinds remain conflict events and country
indicators), `policy-context-layers/1`, a TACITUS-native context, a PRAXIS attachment
or a verified bridge into either project.

It contains:

- A bounded question/task and a digest of the retained three-excerpt/six-record
  baseline. This digest identifies canonical local evidence content, not external
  truth, a signature or the whole PDF's bytes.
- An `evidence` object with the complete document receipt, linked primary excerpts
  and complete selected assertion records. The PDF's separately recorded source
  digest remains attached to every excerpt.
- An explicit selection method, available and selected assertion IDs, retained and
  omitted passage IDs, and every omitted record with a reason. Preset selection is
  a declared research lens, never a relevance score; visitor selection is labelled.
- Record-specific implementation questions, review gaps and non-negotiable
  interpretive boundaries. There is no generated analyst assessment.
- Exact UTF-8 evidence-byte counts and declared limits: six assertions, a 2,000
  character question and a 128 KiB canonical packet. Input files are read with a
  1 MiB ceiling; JSON depth, values, strings and unsafe keys are bounded. Duplicate
  JSON keys, non-finite numbers and unsupported envelopes are rejected.

`validate_selection` compares an imported packet against the trusted local corpus
and the deterministically reconstructed packet, catching altered provenance/text,
dropped qualifiers, review promotion, hidden omissions, additional fields and false
measurements. Schema validation alone cannot establish primary-source accuracy or
the numeric relationships between counts and bytes.

## What byte measurements mean

`available_evidence_bytes` is the UTF-8 length of the canonical evidence object for
the retained receipt, all three selected excerpts and all six editorial assertions.
`selected_evidence_bytes` measures the same object shape after explicit selection,
including complete linked excerpts and qualifiers. `removed_evidence_bytes` is the
difference. Object keys are sorted recursively; arrays retain source order; JSON
uses `ensure_ascii=false`, `separators=(',', ':')` and no trailing newline.

The scope excludes the question, selection metadata, gaps, boundaries and the
measurement object itself. Pretty-printed downloaded file sizes will therefore
differ. These measurements compare **this curated baseline**, not the full PDF or
all political context. They are not token estimates, model costs, semantic coverage,
answer-quality scores or empirical saliency/efficiency improvements. Visitors can
inspect exactly which records were left out instead of treating a smaller packet as
automatically better.

## Browser integration and untrusted text

Import `lab.json` statically. Its `source`, `records`, `passages`, `tasks`,
`gaps_by_record` and `boundaries` require no API. Each task contains a complete,
validated `packet`. Custom browser selection must apply the same record order,
shared-passage retention, omission reasons, boundaries, gaps and canonical byte
serialization as the Python builder; validate exported examples with the CLI.
The standalone generated files contain only public evidence and no authentication.
Private hosting still requires the enclosing site to enforce its access policy.

Render all source text, questions and notes as plain text. Do not evaluate source
content, use it as HTML, execute embedded instructions or let it override agent
instructions. The exporter preserves hostile-looking source strings as inert
evidence; it does not claim that arbitrary source text has been sanitized. If
embedding JSON into an HTML script element, escape HTML script terminators or use a
separate JSON asset; a valid JSON file is not automatically safe HTML.

## Verification

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_policy_document.py' -v
```

The suite checks provenance closure, exact byte accounting, deterministic presets
and mixed selections, shared paragraphs, complete exclusions, input bounds,
malformed JSON, review/implementation boundaries, untrusted source content and the
standard-library CLI. JSON Schema checks use the repository's optional existing
`jsonschema` development dependency and skip only when it is unavailable.
