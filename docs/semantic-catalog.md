# Semantic catalog and source-record graph

The atlas provides five vocabulary lenses over retained source fields, a bounded
**2,048-record navigation sample**, and **188 lazy country/year indexes**. The
underlying collection contains 120,576 UCDP GED 26.1 records for 2000–2025 and a
separate 15,272-value World Bank annual layer. Opening a node can retrieve its
exact original evidence rather than a generated political assertion.

The lenses are **scoped alignments and navigation aids**. This feature does not
run an RDF reasoner, create causal or affiliation claims, certify sources, or
claim compliance with every requirement of the referenced standards. The existing
curated Syria political ontology remains a separate, qualified collection.

## Five lenses

| Lens and primary reference | Concrete source fields | What it reveals and where it stops |
| --- | --- | --- |
| [PROV-O](https://www.w3.org/TR/prov-o/) | Dataset ID, original provider ID, source locator, release/file/record digests | Follow a normalized record to its source release. Lineage is not verification or independent corroboration. |
| [SKOS](https://www.w3.org/TR/skos-reference/) | GED `type_of_violence`; annual `indicator_id` and name | Inspect provider categories and labels. No hierarchy, cross-scheme equivalence, allegiance or credibility is inferred. |
| [OWL-Time, 2017 Recommendation](https://www.w3.org/TR/2017/REC-owl-time-20171019/) | `date_start`, `date_end`, `date_prec`; annual reference year | Preserve reported intervals and uncertainty. No exact event instant or temporal entailment is invented. |
| [GeoSPARQL 1.1](https://docs.ogc.org/is/22-047r1/22-047r1.html) | Provider coordinates, WKT, place labels and `where_prec` | Separate a reported feature from its geometry representation. A point can stand for an area; it is not current control or a boundary decision. No spatial-query engine or conformance suite is implemented. |
| [SOSA / SSN](https://www.w3.org/TR/vocab-ssn/) | Annual economy, indicator, reference period, value and raw/display units | Inspect an actual annual result through the observation/property/feature/result pattern. Values can be estimates; neither sensors nor measurement procedures are asserted. |

The SOSA example is the actual record `wdi:2:SYR:SP.POP.TOTL:2024`: **24,672,760
persons**, the World Bank's annual population estimate for its Syrian Arab
Republic economy category. Its source `unit` is empty; the display unit `persons`
comes from the reviewed indicator metadata. The original empty unit remains
visible. The annual reference year is not an exact measurement day or retrieval
time. The example links to its registered indicator shard and retains the
canonical digest of that shard record's attributes, including attributed metadata.
There is no inferred relationship between this value and a conflict event.

## Versioned assets

The atlas `data/manifest.json` has a `semantic_catalog` descriptor with `format`,
`path`, `bytes` and `sha256`. All semantic paths resolve relative to the atlas
root. Descriptors identify exact file bytes; consumers verify size and SHA-256
before parsing, and apply a 3 MiB read bound. The semantic JSON is ordinary,
schema-described navigation data, not an assertion that it is a complete RDF graph.

| Asset | Format | Contents |
| --- | --- | --- |
| `data/semantic/catalog.json` | `policy-semantic-catalog/1` | Dataset/source snapshot identities, five lens definitions, three provider category concepts, counts, overview descriptor, partition descriptors, actual annual example and limitations. |
| `data/semantic/graph-view.json` | `policy-semantic-graph/1` | 2,048 distinct real GED record nodes, one dataset anchor, three concept anchors and 4,096 source-backed links. |
| `data/semantic/partitions/{country}/{year}.json` | `policy-semantic-partition/1` | Registered compact/full shard descriptors for one provider country/year. Full records and attributes are not duplicated. |
| `ontology/semantic-lenses.json` | `policy-semantic-lenses/1` | Versioned vocabulary references, exact term IRIs, applicable record kinds, field selectors, edge templates and scope limitations. |

The overview uses round-robin quotas over nonempty country/year partitions, then
the first records in numeric provider-ID order. It is **a navigation sample, not
a statistically representative sample** and not the whole corpus. The current
overview is 1,894,397 bytes; the catalog is 60,749 bytes. A full production build
on 2026-11-06 passed schema and size checks; UI/API additions can change the total
hosting package size without changing source data.

Record nodes retain actual `id`, `kind`, dataset ID, label, country lookup code,
date window, coordinates, original record digest, geographic/temporal precision,
provider classification, `compact_shard` and `raw_shard`. Selecting a node resolves
the registered compact part and, when requested, its gzip full-record partner.
The full partner retains all 49 original GED string fields. Validate compressed
and decoded file identities as described in [event provenance](historical-events.md)
and verify the per-record canonical digest before export or further processing.

Overview edges are restricted to two documented relationships:

- `prov:wasDerivedFrom`: the normalized source record derives from the named GED
  dataset release. Evidence selectors are `dataset_id` and `provider_id`.
- `dcterms:subject`: the record carries the provider's explicit violence category.
  The selector is `attributes.type_of_violence`. Its target is the corresponding
  source-specific concept, not an inferred political topic.

Other lens templates describe how a selected record's fields may be displayed.
They do not materialize unsupported inter-record relationships. Geographic
proximity, shared actors, a date match or a common publisher is not upgraded to
causation, control, independence or corroboration.

## Build and verify

`build_observation_atlas` invokes
`semantic_catalog.build_semantic_catalog(repository, output, observation_manifest)`
after the verified event and annual shards exist, then includes the returned
catalog descriptor in the main manifest. No live fetch or model account is needed.
Generated assets refuse a changed existing target; use a fresh output directory.

```sh
python scripts/build_showcase.py --output /absolute/path/to/fresh-output
python -m unittest discover -s tests -p test_semantic_catalog.py -v
python -m unittest discover -s tests -p test_historical_events.py -v
```

The [shared schema](../schemas/semantic_catalog.schema.json) checks the four
formats. Producer checks also verify registered source-part hashes/counts,
whole-corpus totals, allowed vocabulary namespaces, source locators, absence of
duplicate overview IDs, publication scope, byte bounds and safe local paths.
The tests reopen all 2,048 production overview nodes against full real records and
check their original-field digests. Additional tests exercise changed assets,
traversal, missing partners, incorrect totals, unrecognized terms and an unsupported
political relationship. The normal CI test discovery includes these tests.

Changing the navigation sample, schema or lens semantics requires a documented
version change. A new provider release requires new provenance review and a new
dataset/version identity; never silently combine releases. Hashes establish byte
identity, not an independent guarantee that a provider claim is true.
