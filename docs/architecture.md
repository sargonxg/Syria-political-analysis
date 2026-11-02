# Architecture and provenance

The public toolkit validates a versioned JSON corpus and produces deterministic briefs, graphs, tables and a static source atlas. It needs no private database. Country workspaces isolate the public collections; see [country workspaces](country-workspaces.md).

The optional private desk uses FastAPI, SQLite and a browser interface. A case holds sources, stored documents, attributed claims, notes, actors, events and themes. A claim requires an exact excerpt and locator and pins the document revision used. An exact match establishes traceability, not truth. Notes distinguish evidence, assumptions, judgments, alternatives and uncertainty. Links are references rather than corroboration or political control.

SQLite migrations run on startup; optimistic revisions prevent silent overwrite. Exports retain IDs, relationships and history. Restore validates the full case before a transaction and rejects conflicting IDs. Private databases and backups belong outside tracked public data. All holders of the shared key can access all cases: cases are organizational boundaries, not user permissions.

Public source profiles retain ownership unknowns, evidence URLs, qualifications and review dates. A review date is not a publication date. Historical private input identifiers remain optional archival metadata; committed normalized files and actual public citations are sufficient to reproduce the public outputs. Public paraphrases without original passages import as notes, not exact-excerpt claims.

`src/syria_analysis/desk` contains the server and private UI; `data` and `ontology` contain public evidence contracts; `exports/atlas` is the built static directory; `examples` contains explicitly fictional training material. No model-generated findings, arbitrary URL fetcher or live feed is enabled.

The supported container path is one operator, one host, one worker and persistent local disk. It does not supply per-user RBAC, database encryption, a tamper-proof audit ledger or managed cloud infrastructure. Read [deployment and backup instructions](deployment.md) before private cloud operation. Code is MIT licensed and repository data CC BY 4.0, subject to underlying source rights; storing an excerpt does not grant republication rights.
