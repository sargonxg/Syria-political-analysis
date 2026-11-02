# Method and review

An entry in the source directory establishes a documented publishing identity and remit. It does not endorse everything the publisher produces. Institutional self-descriptions are identified as such; they are not independent ownership audits.

## Record stages

| State | Meaning |
| --- | --- |
| `unreviewed_reference` | Title/link or social metadata awaiting a human source check. No mapped incident location. |
| `needs_source_check` | A reviewer has identified missing evidence or an unresolved source question. |
| `curated_paraphrase` | An attributed editorial paraphrase tied to a primary document and locator. It is not independent corroboration. |
| `corroborated` | Requires at least two source entities and a written independence assessment. Different sites may share the same underlying report. |
| `disputed` | A material claim has a documented contradiction that must remain visible. |
| `superseded` | A newer record changes its relevance; the earlier record remains available. |

Nothing in the initial corpus is marked `corroborated`. A compiler cannot establish source independence from a domain count; the validator enforces a minimum structural condition, while the analyst must make and document the judgement.

## Reading a source

1. Open the original publication and check its issuer, date and reporting period.
2. Separate a plan, an announcement, an activity and evidence of an outcome.
3. Record a page or section locator. Preserve the original language when you have permission to store a passage; label a paraphrase explicitly.
4. State the geographic scope in the source's terms. A regional survey is not a city incident.
5. Identify limitations, alternative accounts, dependence between sources and material that remains unavailable.
6. Write an assessment separately. A checked box is not a new finding.

Original passages in this starter dataset are `null`; attributed paraphrases must never be presented as quotations. Some documents were checked through indexed first-party metadata rather than a directly retrievable page; the source verification field records that distinction.

## Geography

The fourteen points are approximate **regional navigation anchors**, rounded to 0.01 degree. Some stand for a city, others for a governorate or a multi-governorate region. They do not identify an incident site, facility, person or current risk. No feed title or social reference is assigned a coordinate. Do not interpret this as a travel-safety map or a tactical layer.

## Time

Publication day, exact feed timestamp, reporting interval, source-check day and collection time have different meanings. For a source known only to the day, `published_on` stores the date and `published_at` stays null. No midnight publication time is invented. A metadata-import timestamp does not mean the full source was downloaded then. Dated material is never automatically promoted to a present-tense finding.
