# Compare media without turning an outlet into a score

The source atlas now includes **Assess framing** and **Data & tools**. It works offline as one HTML file. The selected directory covers 55 publisher/institution profiles; eight data, research and verification resources remain separate. Syria is still the first curated evidence collection. A regional source profile does not make its reporting a Syria event.

Start with a bounded claim, a publication window and comparable genres. A wire report, opinion column and government statement serve different functions. Read each original report before quoting a passage. The worksheet keeps six questions visible: speaker attribution, lead framing, claim support, upstream lineage, unaddressed questions and consequential wording. Ownership and funding records stay next to those observations without becoming an article-level verdict.

## Use the offline application

```sh
python -m pip install -e .
python scripts/build_showcase.py
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8766/sources/`, then **Assess framing**. Choose two publishers, enter original URLs and selected passages, and keep an interpretation, alternative explanation and missing evidence separately. A repeated upstream URL is flagged as a shared entered reference, not independent corroboration. Switching a publisher clears only that report's fields; prior quotations cannot silently inherit a new attribution. Notes remain in the tab until an explicit download. No browser API calls or automatic article scraping occur.

The **Entered evidence trail** draws only the relationships in your worksheet: selected publisher → entered report, report → entered quotations, and report → named upstream URL. Select a record with a pointer or Tab and Enter/Space to inspect exact wording, locators and original URL entries. Repeated upstream URLs share one node after fragments and common tracking parameters are removed; distinct paths remain distinct. The text connection list provides the same relationships without interpreting a diagram. On narrow screens the diagram scrolls within its own panel.

Your interpretation appears as a separate, unreviewed node. It has no evidence-support edge: the current worksheet does not record which individual claim supports an interpretation. A report-level upstream URL is not silently assigned to each quotation either. Empty fields produce no quotation/reference relationship, and changing a publisher removes that report's entered trail. The diagram is a derived view; the `media-framing-assessment/1` export contract is unchanged and remains the source of the entered records.

See [0.3.1 verification and limits](entered-trail-verification.md) for the tested provenance, keyboard, mobile and export behavior.

The source directory includes recorded first-party disclosures and partial institutional evidence. Funding/ownership unknowns remain unknown. No political-bias, credibility or reliability score is calculated. An omitted question in a selected report does not establish intent or the character of an entire outlet.

## AI-readable comparison contract

```sh
policy-analysis compare-sources --left syria-direct --right sana \
  --question "How is this selected political claim framed?" \
  --output output/comparison.json
policy-analysis compare-sources --left syria-direct --right sana \
  --question "How is this selected political claim framed?" \
  --format markdown --output output/comparison.md
policy-analysis resources
```

`media-framing-assessment/1` contains the exact two source profiles, their evidence, two separately attributed report records, the six comparison dimensions and an unreviewed analyst assessment. It is described in `schemas/media_assessment.schema.json`. The CLI creates a blank worksheet; it neither generates an answer nor classifies an outlet's politics. It rejects unknown/identical sources, missing questions, public-reference URLs with embedded credentials/private hosts, and falsely recorded human review. Markdown binds reports by source ID even if arrays are reordered.

Both browser and Python exports identify the hash serialization used. The snapshot digest covers the selected publisher profiles, not the analyst notes or complete downloaded file; it is not an external signature or a factual verification.

## Sources and pipeline access

Three additional publisher-disclosed RSS endpoints—Daraj, MERIP and SJAC—were retrieved and XML-parsed in a bounded check. Eight feeds are registered in total. The saved reading sample remains the earlier five-publisher snapshot; no new article bodies, social posts or regional event coordinates were collected by this revision. Run collection deliberately and review geographic scope before adding references to a country workspace.

The resource directory records actual access prerequisites: ACLED needs authenticated/OAuth access; UCDP an issued token; ReliefWeb an approved `appname`. HDX's metadata endpoint returned JSON during the dated check; GDELT returned an unavailable response. None is advertised as a continuously connected service. Preserve each dataset's own licence and access rules; a reachable endpoint is not a redistribution licence.

Institutional evidence checks on the added profiles are recorded in the UTC calendar on 5 November 2026 (4 November in New York). `review_actor_type` records automated research assistance; no human journalistic or financial audit is claimed. Partial records remain visibly qualified. Existing analytical claims, dates and normative resolution-2254 drafts were not promoted or rewritten.

## Cloud, private cases and engineering references

`wrangler.jsonc` publishes only `dist/` as Cloudflare Static Assets. Follow `docs/context-layers.md` for commands. No secrets or private cases belong in that directory. The optional authenticated FastAPI/SQLite desk remains a separate local or single-instance container deployment, documented in `docs/deployment.md`; the static atlas does not expose its database.

Useful architectural/method references:

- [SJAC Bayanat](https://github.com/sjacorg/bayanat): a distinct AGPL evidence-workflow project, with linked records, revision history, review roles and geospatial capabilities. Its code was not imported or its runtime verified here.
- [Bellingcat toolkit](https://github.com/bellingcat/toolkit): first-party tool-discovery reference; check each tool's scope and terms.
- [Berkeley Protocol](https://humanrights.berkeley.edu/publications/berkeley-protocol-on-digital-open-source-investigations/): digital-investigation methodology; no formal certification is implied.

This toolkit remains a bounded research aid. Source text is untrusted data for an AI workflow, never an instruction that overrides the researcher's task.
