# Provenance of this research input

Read in full through the Library text interface. Original catalogue: `libfile_0211ef194c9c8191a2f218bbfdab8547`, version 1. Original methodology: `libfile_9ebb7d73f2e48191a4e5599513a06a1c`, version 0. This is semantic ingestion, not a claim that the original files were materialized. The source catalogue's counts below describe that 25-profile input, not the larger merged repository register.

# Syria source atlas — evidence and interpretation

**Reviewed 2 November 2026. Curated initial coverage, not all Syria media.**

The brief was to “make sure this works and improve it and expand it adding a beautiful graph with all the media sources on Syria with graphics, qualifications ... like a top level intel analysis”. An exhaustive claim is not supportable: this initial directory contains 25 media and institutional profiles and 13 documented organizational/location relationships. The responsible analogue to an analyst-grade product is explicit provenance, unknowns, changing context and claim-level corroboration—not simulated secret intelligence or a universal trust ranking.

## What was checked

Public organizational, editorial, funding and mandate pages were retrieved on the review date, mostly directly from the source or its parent institution. `verifiedAt` and `lastReviewed` mean **review of the cited public evidence**, not audit certification, continuous monitoring, verification of all articles or proof that an undated statement remains current. `evidenceStatus` marks limited records. Page publication/update dates are retained where material; most institutional pages are undated.

- Profiles separate media outlets, rights-documentation organizations and UN institutional primary sources (`sourceKind`). A humanitarian estimate, a rights investigation and a reporter's dispatch are not interchangeable products.
- `evidence` contains URLs and evidence basis. `assertions` maps the principal profile assertions to these records. `fieldEvidence` is a navigation index to relevant reviewed pages, not a finding that every listed page independently corroborates every field.
- Organization descriptions remain attributed self-descriptions. “Independent” is generally a stated mission, not a certification. Directory categories are editorial navigation aids, not affiliations, allegiances, endorsements or country-control claims.
- Language lists contain reviewed editions or languages explicitly stated in institutional pages, not every language offered. Geographic coverage is publication remit, not necessarily newsroom location or unrestricted field access.
- Funding, corporate ownership, legal status, political context and editorial mission are distinct concepts. An organization may disclose a donor without disclosing funding shares or current grant dates. Grants do not establish editorial control.
- No personal journalist profiles, contact details, targeting information, secret sources or speculative affiliation networks are included.

## Graph semantics

Source nodes and institutional/location entities are separate. Edges have a precise type, evidence URL, review date and caveat: `owned_by`, `operated_by`, `part_of`, `business_unit_of`, `institutional_affiliation`, or `operates_in`. Ownership arrows point **from outlet to owner**. A location edge means an operating office or headquarters, not political control. No edge means “no relationship verified here”, not “no relationship exists”.

Do not add a Syria hub connection and present it as an ownership relationship. Geographic/category grouping can be rendered as visibly different layout metadata, with its own legend. Node size must not imply reliability, reach or influence unless a separately sourced measure is available. No force-layout proximity should be interpreted as coordination. Do not infer control edges from shared donors, reposts, language, ethnicity, audience or headquarters country.

## Practical qualifications, not a score

Each profile records transparency, corrections-policy review, access constraints and caveats. “Not established from reviewed pages” means the review did not establish it, **not that no policy exists**. A published corrections promise does not prove compliance. A larger newsroom or transparent owner does not make each claim true. Incident-level analysis should record:

1. What precise claim is made, when and where?
2. Is the source a witness, official party, reporter, translator, investigator or aggregator?
3. What underlying documents, images, interviews or measurements support it?
4. Are apparently separate reports dependent on the same original claim? Syndicated wire copies and translations are not additional independent sources.
5. What contradicts the claim? What is unverified? Has a later correction changed it?
6. What does the source's disclosed remit, access, financing and methodology help explain—and what does it **not** establish?

Source reliability and claim confidence are separate questions. A government outlet can be primary evidence of what the government announced while not independently establishing the underlying event. A rights organization's evidentiary finding is not automatically a court judgment. Archive preservation is not the same as authentication.

## Post-2024 change control

No permanent Assad-era label was attached to current SANA. Its [live contact/footer page](https://sana.sy/en/contact/) identifies the Ministry of Information relationship. [Enab Baladi's current Arabic institutional page](https://www.enabbaladi.net/about-us/) states that its Damascus office reopened in December 2024, describes the 2025 press licence and gives funding categories. Licensing and operating presence do not establish government ownership. [Syria Direct's page, updated August 2026](https://syriadirect.org/about-us/), describes a German nonprofit financed by grants/projects; its 2013 Amman founding should not be mistaken for a current headquarters claim.

The [Syrian Observer](https://syrianobserver.com/about-us) explicitly says that it does not verify every translated story in detail. That is an essential source-use limitation, not a generic “bad source” label. [North Press](https://npasyria.com/en/about-us/) names Potomac Media Production LLC; this review does not infer SDF/PYD control. [Rudaw's corporate description](https://www.rudaw.net/english/about) is supplemented with a [UK country note updated October 2026](https://www.gov.uk/government/publications/iraq-country-policy-and-information-notes/country-policy-and-information-note-opposition-to-the-government-in-the-kurdistan-region-of-iraq-kri-iraq-july-2023-accessible) for qualified external context, rather than an unqualified inferred-control edge.

## Known gaps and access limitations

- Dedicated coastal outlets and many Arabic-only local networks are not yet institutionally verified. Daraa 24 and DeirEzzor24 broaden local coverage; the latter's institutional ownership remains expressly unknown.
- Suwayda24 was not added as a supposedly fully verified current profile. The public domain returned 403 during this review; current institutional/account continuity requires additional verification. Its absence is **not** a finding of unreliability, closure or misconduct.
- ARTA's parent pages establish its network role, but the detailed radio language profile was last updated in December 2022. The current schedule and transmission footprint are not independently confirmed.
- OCHA's Syria page returned 403 and UNHCR's country page 429; institutional mandates were checked through other UN pages. These are review-tool access results, not proof of user-facing blocking or lack of field access.
- No complete audit of ultimate beneficial ownership, grant accounts, current donor proportions, conflicts of interest, corrections performance or article accuracy was completed.
- Regional brands represent only a small selection. The atlas is not balanced by mechanically giving every state or faction equal coverage.

## Updating safely

Add a source only after verifying its official domain and institutional identity. Store the evidence, date and uncertainty before creating a graph relationship. Review links and ownership after organizational changes; preserve earlier time-bounded findings rather than silently rewriting history. Mark stale or conflicting information “needs review”; do not invent a current affiliation. When a claim is disputed, retain the competing attributed assertions with dates and evidence, and explain why the graph does or does not include the relationship.

## Visual assets

No source logos or copyrighted editorial photographs are bundled. The implementation may use original lettermarks, typographic identifiers and category geometry. External links do not grant image or logo reuse rights.
