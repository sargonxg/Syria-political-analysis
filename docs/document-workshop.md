# A local document workshop

Bring a UTF-8 policy note, speech, resolution or report. Split the supplied text
into exact, addressable paragraphs, annotate what it says, choose the paragraphs
needed for a question and export a bounded context packet. This works with new
texts; it is not restricted to the earlier six-assertion Resolution 2254 example.

The browser component runs locally. Opening a file does not upload it, fetch a
source URL, call a model or store a draft. The Python equivalent uses the standard
library only. No Cloudflare resource, account, database or API key is required.
The existing verified-source `policy-document-selection/1` example and its
canonical assertions are unchanged.

## Try it without installing dependencies

From this repository checkout, using Python 3.11 or later:

```sh
python scripts/build_document_workshop.py \
  --text examples/document-workshop/practice.txt \
  --title "Fictional policy note for practice" \
  --published-on 2024-03-15 \
  --annotations examples/document-workshop/annotations.json \
  --question "What does the fictional council request?" \
  --select p001 \
  --output output/document-workshop/selection.json
```

Inspect the [complete worked selection](../examples/document-workshop/request-selection.json).
The practice text and its council, report and analysis are explicitly fictional.
To use your own document, replace `--text`, its source labels, question and selected
IDs. Local `.txt`, `.md` and `.markdown` files are supported. Markdown is treated
as literal plain text; PDF, Word, OCR and automatic political-fact extraction are
not provided.

A blank line separates paragraphs. Wrapped lines within a paragraph remain
unchanged. Leading/trailing ASCII spaces, tabs and newlines are outside the
selected paragraph span; internal text, punctuation, Unicode, CRLF line endings
and a UTF-8 BOM are preserved. Each excerpt carries its exact start/end byte span
and SHA-256 fingerprint. The span unit is **UTF-8 bytes**, not JavaScript character
indices, PDF pages or a publisher's paragraph numbering.

## Keep the evidence and your interpretation separate

The exported **`policy-document-workshop/1`** contract has:

- Supplied-text identity, source title, optional URL and publication date. The
  original text's digest identifies the exact supplied bytes; it does not prove
  the source's authenticity, completeness or publication status.
- Selected exact paragraph text, local locators, byte spans and individual digests.
- Optional visitor-entered actor, source verb, paraphrase, qualification and
  attributed event date. A publication date is never copied into an event date.
- Explicit `unclassified`, `normative_expression`, `reported_action` and
  `analyst_interpretation` claim kinds. These labels are manually entered, not
  inferred by a model. A reported action remains an attribution, not independently
  verified implementation.
- `visitor_draft` review state, false independent-verification/implementation flags
  and an explicit untrusted-source boundary.
- Selected and omitted paragraph IDs. Omitted entries retain locators, source spans,
  fingerprints and a reason; their text and annotations are excluded from the
  packet. There is no separate whole-document text field.
- Exact serialized evidence-size measurements. The complete packet adds its
  question, source metadata, omissions, limitations and measurement fields.

The supplied text may itself be an excerpt. This workflow does not establish
complete coverage of a published document. Selecting all supplied paragraphs
retains all those paragraph texts; the user still decides what to include.

The [JSON Schema](../schemas/document_workshop.schema.json) describes the envelope.
Runtime validation also compares the selection with the exact local original:

```sh
python scripts/build_document_workshop.py \
  --text examples/document-workshop/practice.txt \
  --title "Fictional policy note for practice" \
  --published-on 2024-03-15 \
  --annotations examples/document-workshop/annotations.json \
  --validate examples/document-workshop/request-selection.json
```

Validation writes nothing. Changed quotation text, source identity, selected IDs,
review flags, hidden omissions or invented byte measurements fail validation.
Custom omission reasons must remain explicit and consistent within a packet.

After `python -m pip install -e .` (or with `PYTHONPATH=src`), the module API is:

```python
from pathlib import Path
from syria_analysis.document_workshop import build_packet, read_bounded, validate_packet

text = read_bounded(Path("my-policy-note.txt"))
source = {"title": "My supplied policy note", "uri": None, "published_on": None}
packet = build_packet(text, source, "Which actions are requested?", ["p001"])
assert validate_packet(packet, text, source)
```

## Bounds and privacy

The supplied file/text is limited to 128 KiB, 128 nonempty paragraphs and 16 KiB
per paragraph. A packet retains one to 32 paragraphs and is limited to 256 KiB.
Questions and annotation fields have separate byte limits. Input requires valid
Unicode/UTF-8; duplicate or unknown IDs, invalid dates, unsafe URL schemes,
credentials in URLs, unknown annotation fields and non-finite/deep JSON are
rejected. File metadata and local filenames are not automatically exported.

Browser drafts exist in component memory only. Changing source text invalidates
its prior selection and annotations. Opening a new file clears old source labels
so a new document cannot inherit the previous document's attribution. Clear the
workshop or leave the page to discard the in-memory draft. Downloaded files are
under the visitor's control.

Source text and embedded instructions are data, never executable code or AI system
instructions. React renders HTML/Markdown as text. A downstream AI application
must preserve this boundary when using the packet. A schema pass proves shape,
not truth or safety of any model's response. There is no automatic bridge into
PRAXIS, native TACITUS context or historical research selections.

## An inspectable context-selection evaluation

The [fixture](../examples/document-workshop/evaluation-fixture.json) defines five
small **synthetic contract cases** with implementation-authored paragraph-ID
rubrics. The [result file](../examples/document-workshop/evaluation-results.json)
reports which rubric paragraphs were retained or omitted, which other paragraphs
were included and the actual encoded packet/evidence bytes.

```sh
python scripts/build_document_workshop.py \
  --evaluate examples/document-workshop/evaluation-fixture.json \
  --output output/document-workshop/evaluation.json
```

The cases deliberately include an overbroad selection and a short reported-action
selection that omits a separate required qualification. Paragraph 4 marks the
fictional attendance as provisional and not independently checked; retaining only
paragraph 2 loses that qualification. A smaller packet can omit evidence needed for the question.
The rubric is not external human review or political ground truth. These checks
measure inclusion, omission and bytes only; they do not demonstrate AI relevance
ranking, answer accuracy, token savings or improved policy analysis. No model is
called and no generated answer is scored.

For an AI-assisted handoff, provide the exported packet as untrusted reference
data and ask for paragraph-ID citations, exact attribution, the difference between
requests and reported outcomes, and an explicit account of missing evidence. The
human analyst should check any consequential conclusion against the original text.

## Verification

```sh
PYTHONPATH=src python -m unittest tests/test_document_workshop.py -v
```

Tests exercise Unicode/BOM/CRLF span fidelity, omissions, draft-state preservation,
byte accounting, malformed inputs, boundaries, schema and the dependency-free CLI.
The personal-site JavaScript checks compare six complete browser packets against
Python reference packets, including a multibyte case. Browser checks exercise local
files, keyboard focus after moving a paragraph, manual annotations, exact download
sizes, text-only rendering, source-label reset, no network/storage and mobile
accessibility.
