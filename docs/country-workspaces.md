# Country workspaces

Syria remains the first curated collection, at the existing root data paths. The GitHub repository name and `syria-analysis` command are retained for existing links and scripts. `policy-analysis` calls the same implementation. `--country` explicitly selects a registered workspace; an unknown code fails rather than falling back to Syria.

```sh
policy-analysis countries
policy-analysis --country SY validate
policy-analysis init-country --code LB --name Lebanon --region "Middle East"
policy-analysis --country LB validate
policy-analysis --country LB build-context
policy-analysis --country LB ontology --format jsonld
```

`init-country` creates `countries/lb/` with empty source, document, claim, place, context, social and political records. It adds a profile in `data/countries.json`. Its status is `empty_framework`; this does not claim that Lebanon has been researched. Initialisation rejects an existing country or directory and does not overwrite data. Registry paths must resolve inside the repository, including through symlinks.

The same JSON Schema contracts in `schemas/` apply to every country. Shared political classes and relationship definitions live in `ontology/core.json`; each country has its own `data/ontology/module.json`, concepts, entities, assertions and review ledger. Country-specific concepts require terminology sources and scope notes. A Syria-specific term such as “Syrian-led and Syrian-owned process” does not automatically belong to another country's vocabulary.

Relative export paths resolve within the selected workspace: Lebanon context goes to `countries/lb/exports/context.json`, while Syria retains `exports/context.json`. Absolute output paths remain supported. A context pack contains its country envelope. Political RDF instance identifiers include the country code, for example `urn:policy-analysis:SY:assertion:...`; vocabulary class/property identifiers remain shared. JSONL carries the country, vocabulary definitions, concepts and qualified assertions as well as the original source tables.

Before activating a collection, register real sources with profile evidence; verify actual feed endpoints; review primary documents; establish geographic and temporal scope; then create attributed claims. Sources about multiple countries may be registered deliberately in several workspaces. Cross-country comparison requires explicit scope reconciliation and source-independence review; concatenating exports does not establish a regional finding.

The website currently displays the Syria collection. The framework is extensible; no other country collection or scheduled regional coverage is represented as completed.
