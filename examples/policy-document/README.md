# Policy-document worked selections

These are actual source-qualified selections from resolution 2254 (2015), not generated political outcomes or native PRAXIS capsules. Each contains the unchanged document receipt, selected primary excerpts, full draft assertion objects, source fingerprint, omissions, implementation gaps and byte measurements.

| Task | Assertions | Paragraphs | Selected evidence bytes |
| --- | ---: | --- | ---: |
| [Negotiations](negotiations.json) | 1 | 2 | 5,277 |
| [Institutions](institutions.json) | 4 | 4 | 11,529 |
| [Ceasefire](ceasefire.json) | 1 | 5 | 5,184 |

The three-excerpt/six-assertion evidence baseline is 18,958 canonical UTF-8 bytes. These numbers measure the `evidence` object only; complete packets include additional question, selection and limitation metadata. They are not token estimates or measured analytical gains.

Human review remains pending. Paragraph 5 is only part of the ceasefire framework; the full instrument, including paragraph 8, and separate implementation evidence remain necessary. See [the walkthrough and contract](../../docs/policy-document.md).

Reproduce all three files from the repository root:

```sh
python scripts/build_policy_document.py --output output/policy-document
python scripts/build_policy_document.py --validate output/policy-document/negotiations.json
```

No keys, live collection or model access are needed. Public document excerpts retain their source attribution; the repository's MIT code licence does not transfer rights to third-party source material.
