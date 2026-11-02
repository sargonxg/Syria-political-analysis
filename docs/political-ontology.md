# Syria political research ontology

This is an independent research vocabulary, not an official UN ontology or a current assessment of Syria. Canonical JSON preserves the existing evidence tables. A shared model in `ontology/core.json` defines 17 types and 15 relations; `data/ontology/module.json` adds eighteen Syria-scoped analytical concepts, terminology sources and qualifications. The initial seven entity records and six assertion drafts demonstrate the model with resolution 2254 (2015).

## What the model distinguishes

- A publishing profile, a public political actor, an institution and a public office-holder are distinct records. A source's publishing identity does not establish political affiliation.
- A legal instrument, an actual political process, an episode and a normative objective are distinct types. The 2254 examples use `NormativeObjective`: a requested action or supported arrangement is not an observed outcome.
- A concept is a reading category. Labels such as inclusion, civil society, representation and governance do not instantiate actors or establish their legitimacy.
- A source document has its original publication date. A local document receipt has its collection metadata. Neither date is silently substituted for an event date.
- A political relationship is an attributed assertion with a subject, relation, object, source verb, temporal scope, evidence locators, qualifications and review state.

The vocabulary covers political processes, good offices, mediation, formal negotiations, governance, constitutional and electoral processes, inclusion, women's participation, representation, civil society, consultation, mandates, legal instruments, accountability, protection and displacement. Some institutional terminology references were available only through first-party indexed descriptions; the module records those access limits. They do not establish current operations, membership or implementation.

## The dated working example

The [official four-page resolution](https://documents.un.org/doc/undoc/gen/n15/443/34/pdf/n1544334.pdf), adopted **18 December 2015**, was read for the six assertion drafts. Operative paragraph 2 **requests** convening formal negotiations; paragraph 4 **expresses support** for a Syrian-led process, governance, constitutional drafting and elections; paragraph 5 expresses support for a condition-linked ceasefire. Paragraph and printed-page locators accompany every draft. Conditions and target language remain in the records without calculated implementation dates.

All six drafts remain `needs_source_check`, with `human_review_recorded: false`. An automated primary-text check does not become a completed human review. The review ledger starts empty. A later human-review assertion needs a matching review activity, reviewer, day and rationale. Political corroboration requires distinct publishing entities and an independence assessment, just as the existing textual claims do.

## Export semantics

```sh
policy-analysis --country SY ontology
policy-analysis --country SY ontology --format jsonld
policy-analysis --country SY build-context
```

PROV-O describes record provenance. SKOS describes the controlled concept scheme. Dublin Core describes documents. Local political relations preserve their domain meaning: `dcterms:mediator` is not used for peace-process mediation, and `prov:wasInfluencedBy` is not used for political influence.

JSON-LD 1.1 uses an inline context and country-qualified `urn:policy-analysis:SY:...` identifiers. The URNs are identifiers, not claims that a public vocabulary server exists. Classes and property definitions are included. `policy:allowedDomainType` and `policy:allowedRangeType` list permitted alternatives; multiple RDF `rdfs:domain` statements would incorrectly imply intersection.

Political assertions are reified `rdf:Statement` resources. Their subject/predicate/object name the attributed statement; **the unqualified political triple is not emitted**. The statement retains modality, source verb, time scope, qualifications, evidence and review status. Source resources and local receipts have different identifiers and date properties. JSONL includes vocabulary definitions so concept and relation identifiers remain interpretable without another file.

Validation checks country identity, known entities/relations, domain/range, evidence provenance, source publication dates, required role qualifiers, normative-versus-implementation distinctions and human-review provenance. JSON Schema contracts and offline JSON-LD expansion tests check the serialised forms. This is a validated JSON/JSON-LD research model; it does not claim an OWL reasoner, SHACL validation or automated geopolitical conclusions.
