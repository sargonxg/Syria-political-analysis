# Document semantics and bounded context

This portable ESM pipeline connects exact source spans, unreviewed assertions, typed entity/relation definitions, and explicit task profiles. It runs in Node or the browser without a model, API key, database write or document-upload service.

## Run the cited example

```sh
node --test cloudflare/document-context.test.mjs
node cloudflare/semantic-cli.mjs --example data/semantic-documents/unsc-2254.json --task governance --budget 16000 --output new-semantic-output
```

Outputs: source decomposition, exact context JSON, reified JSON-LD, Markdown review worksheet, and byte/checksum receipt. The destination must be new. Input JSON is capped at 512 KiB; source text at 32 KiB UTF-8.

The example links the repository's six existing assertion drafts to selected operative paragraphs 2, 4, 5 and 8 of Security Council resolution 2254 (2015). It reuses the independent research ontology's 17 classes, 15 relations and 18 country-scoped concepts; it does not claim an official UN ontology.

The English source text is a whitespace-normalized excerpt, not the complete PDF. It retains the original primary PDF URL and SHA-256, its own text SHA-256, paragraph/page locators, and explicit UTF-16 source offsets. Offsets index the retained transcription, not PDF bytes. The source drafts remain `needs_source_check` with no recorded human approval.

The pinned transcription can also be verified directly against the primary PDF with Poppler’s `pdftotext` installed:

```sh
python scripts/verify_semantic_transcription.py --pdf path/to/n1544334.pdf
```

The verifier checks the primary PDF hash before parsing, reconstructs the declared normalized paragraphs and checks every UTF-16 span. It refuses a different PDF or transcription instead of replacing the example. This verifies source-text consistency, not political interpretation or human approval.

## A useful review workflow

- Inspect the source paragraph behind a proposed claim.
- Inspect the relation's allowed subject/object types and the concept's scope.
- Choose mediation preparation, governance, ceasefire scope, or all retained assertions.
- Compile an exact-budget packet retaining whole passages, qualifications and declared dependencies.
- Export a worksheet for analyst review, or JSON/JSON-LD for another tool.

The four governance assertions share operative paragraph 4, which is retained once. The ceasefire proposal carries paragraph 8 as required context; the scope exception is not discarded to make a smaller packet. No target date is converted into a verified implementation date.

Selection follows the declared task profile in order and greedily packs complete assertion closures. This is transparent profile selection, not model-ranked semantic retrieval. An assertion closure includes its exact evidence, required context, entity/type definitions, source identity, temporal scope and qualifications. An insufficient budget refuses rather than shortening the required text.

## Local text

```sh
node cloudflare/semantic-cli.mjs --text authorized-source.txt --budget 8000 --output new-local-review
```

This separate path proposes paragraphs containing literal triggers such as “requests”, “shall”, “must”, or “may”. It retains exact source spans and a source hash. It does not resolve actors, determine legal force, infer whether a sentence is negated, recognize every condition, or extract approved political facts. The output type is `TextualProposal`; issuer and publication date remain unknown. No trigger means no candidate, not a fabricated assertion.

The company interface runs this path entirely in browser memory. It performs no request containing the pasted text and stores no draft in localStorage. Export is an explicit user action. Local source rights remain the user's responsibility; no rights transfer is inferred.

## Graph semantics

JSON-LD reifies each source-attributed claim as an `rdf:Statement`. It includes provenance, literal source verb, review state, qualifications and temporal scope; it does not emit the bare political relation on its subject. Type/property definitions and referenced SKOS concepts are carried in the graph. Allowed domain/range alternatives use local properties, rather than multiple RDF domains with unintended intersection semantics.

PROV-O, SKOS, RDF/RDFS and Dublin Core give the export familiar vocabulary. This is not a claim of OWL entailment, SHACL validation or an authoritative political knowledge base.

This semantic context format is separate from native DIALECTICA capsule archives and from any PRAXIS attachment bridge.

## Structural benchmark

```sh
node scripts/benchmark_document_context.mjs examples/document-context/benchmark.json
```

Sixteen developer-visible profile/budget cases use one cited fixture, one warm-up and five measured repeats per success. The report checks deterministic bytes, exact source spans and retained dependencies, and records insufficient-budget refusals.

The 16,000-byte governance case retains four proposals and one shared passage in 9,045 bytes. A declared inline-evidence representation of the same selected annotations is 11,616 bytes: shared-span references avoid 2,571 repeated bytes. This compares explicit JSON representations, not a packet to raw source text. It does not establish token savings, semantic extraction accuracy, saliency, model-answer quality, inference cost or Cloudflare latency.

`document-context.test.mjs` also tests source/span corruption, domain/range violations, false review approval, unknown vocabulary, Unicode offsets, empty candidate sets, and the absence of bare political triples.

