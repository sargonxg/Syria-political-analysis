# Evidence graph

Generate JSON for a web application or GraphML for tools such as Gephi, Cytoscape or a compatible graph importer:

```sh
syria-analysis export-graph --format json
syria-analysis export-graph --format graphml
```

Node types: `source`, `document`, `claim`, `place`, `context`, `analytical_layer`.

| Directed edge | Meaning |
| --- | --- |
| source → document · `publisher_of_record` | The registered source is the publishing institution; the record also retains the specific publisher label. |
| document → claim · `basis_for_attributed_paraphrase` | The document and locator support an attributed editorial paraphrase. |
| claim → place · `describes_region` | The claim concerns the stated region; the point is a navigation anchor. |
| document → context · `context_reference` | The context record cites the document. |
| context → source · `suggested_reading_source` | Editorial reading recommendation, not corroboration. |

`analytical_layer_reference` links a document to a source-backed analytical lens. The separate coverage export uses publication and explicit title-term edges; it does not add causal links.

Do not infer source ownership, political alignment, affiliation, control or causality from these edges. Two claims citing the same document are dependent observations, not independent corroboration.

The initial graph has no person-to-person or political-actor influence network. Extend it only with typed, source-backed relationships and explicit temporal scope. The public exports require no Neo4j or other hosted service; they are portable data, not a claim of a running integration.
