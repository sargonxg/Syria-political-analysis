# Coverage, framing and analytical layers

The coverage export is a reading aid for a bounded sample. It is built from saved feed references and selected manually registered news references, with their original URLs, dates and review states. It does not read article bodies or rank sources.

## What a line means

- `published_reference`: the source issued the linked saved reference.
- `title_keyword_match`: a literal English/Arabic term from the versioned lexicon appears in the title. The edge preserves the matched term.
- `title_place_mention`: a place term appears in the title. This is not an event location or a coordinate.

Normalization folds case, removes combining marks and common Arabic orthographic differences, then matches word boundaries. It can miss inflections, synonyms and context. A negative statement can still mention a term. Unknown topics and places remain unknown. The method is deliberately inspectable; a model has not inferred sentiment, reliability, affiliation or causal influence.

## A fair comparison

Counts reflect this sample's collection windows, saved references and selected sources. They are not a representative survey of Syrian media or public opinion. No reference in this collection does not mean a source ignored a subject. Different outlets may share an underlying statement; two languages from one publisher do not create independent corroboration.

The curated comparison file provides two concrete reading exercises: SANA's Arabic and English reports of banking meetings in Paris, and a broader comparison of SANA's institutional banking coverage with Syria Direct's household-access questions. The second comparison concerns a shared policy field rather than the same event. Its purpose is to ask what each account foregrounds and what additional evidence a researcher needs. No translation, syndication or influence relationship is asserted without explicit evidence.

## Eight analytical lenses

The layer register separates political process, protection/accountability, displacement/returns, services/recovery, economy, regional relations, security questions and source ecology. Each entry supplies dated primary reading, research questions and a mapping policy. Some institutional context should stay unpinned. Local programme reports can support a regional navigation anchor, with their reporting period and scope preserved.

The 2 November 2026 UNHCR Protection Factsheet covers January–September 2026. Its publication date must not be mistaken for the date of every activity or for a current situation report. The additional Nawa, Al-Hasakeh, Qamishli, Douma and Al-Bab anchors retain these distinctions. Qamishli and Raqqa share a programme reference; do not add a combined total twice.

## Rebuild

```sh
syria-analysis validate
syria-analysis coverage
syria-analysis build-context
syria-analysis export-graph --format json
syria-analysis export-graph --format graphml
syria-analysis export-csv
python -m unittest discover -s tests -v
```

The manual collection workflow uploads these exports for review. Nothing is scheduled, automatically published, or promoted from a headline to a verified incident.
