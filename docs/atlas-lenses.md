# Atlas queries and context lenses

The historical atlas provides a map, source directory and five readings of actual
source fields. It does not run a model or infer political relationships. Open the
generated `/observations/` page through a local HTTP server or the deployed static
site. Country, period and recorded-side filters apply to historical event records;
annual country indicators remain a separate collection.

## Query a snapshot or an available database

The default **Verified static snapshot** loads integrity-checked local partitions.
Enter a literal recorded actor/side name and choose **Apply query**. **Full
history** expands the period to the country collection’s actual bounds. Category,
location precision and general record search are available in the disclosure
below the primary controls. A missing observation is not zero or evidence that no
event occurred.

Database mode is offered only when the served manifest explicitly declares a
same-origin `query_api` and its read-only status endpoint reports availability.
Choose **Connected database** deliberately. Country, overlapping dates, recorded
actor, violence category and geographic precision run on the server. The map and
directory show a bounded page of at most 200 returned records, with the total
matched count and cursor navigation displayed separately. General directory
search filters the returned page only. The source label distinguishes a deployed
D1 backend from a local SQLite development adapter.

A failed chosen database query clears its results and displays an error. It does
not silently run a static query instead. Retry or explicitly select the static
snapshot. Native/static mirrors without an API remain useful and make no probe
to an unconfigured endpoint. The optional database-workspace link is a normal
navigation link; no cross-origin API or service token is used.

Static original-field inspection verifies transferred bytes, gzip decoding bounds,
decoded bytes, record count, identity and the canonical digest of all 49 original
UCDP strings. Database detail checks the returned record against the server’s
declared snapshot and canonical original-field digest. That is a different trust
basis, not static-manifest transport authentication. Both preserve original values
and retain provider low/best/high estimates without repairing them.

## Five source-qualified lenses

| Lens                                                 | Concrete source reading                                                                                                         | Policy use and boundary                                                                                                                                                     |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [PROV-O](https://www.w3.org/TR/prov-o/)              | Provider release, record identifier, source locator and original-field identity.                                                | Trace a comparison to its evidence objects. Lineage does not establish verification, source independence or corroboration.                                                  |
| [SKOS](https://www.w3.org/TR/skos-reference/)        | The provider’s three violence-category codes and definitions.                                                                   | Compare classifications within the documented scheme. No automatic exact/equivalent mapping to another vocabulary is asserted.                                              |
| [OWL-Time](https://www.w3.org/TR/owl-time/)          | The actual event interval and provider date-precision code.                                                                     | Read chronology at its supported resolution. Event time is separate from publication, retrieval and political validity.                                                     |
| [GeoSPARQL](https://www.ogc.org/standard/geosparql/) | Source coordinates and location-precision category.                                                                             | Inspect whether a point represents a named location or a wider area. No topology, territorial control or legal boundary is inferred.                                        |
| [SOSA / SSN](https://www.w3.org/TR/vocab-ssn/)       | An actual World Bank annual series with country, property, year, value, original unit/status and metadata-derived display unit. | Preserve the statistical observation’s context. GED records are not cast as sensor observations; no sensor, instrument, exact measurement instant or causation is invented. |

Select a point or use **Browse lens records** for keyboard/touch navigation. The
source inspector resolves its underlying event or annual value. The clickable
path exposes the dataset, exact record identity and fields used by that reading.
Policy-use notes describe research questions, not generated findings.

Graph positions are an interface layout: horizontal position follows recorded
start date or source year, while vertical groups follow the displayed source
field. They are not a second geographic position or a causal graph. Only a
selected field path is highlighted. The catalogue documents vocabulary alignments;
the browser does not certify full standards compliance or perform reasoning.

The optional **Source navigation index** contains 2,048 real GED record nodes plus
dataset/concept anchors. It is a **nonrepresentative navigation sample**, selected
by the declared round-robin country/year method, not the whole collection or a
sample for statistical estimation. Current event filters do not filter this index.
Its JSON and catalogue are loaded lazily and checked against their manifest SHA-256
and byte lengths. The SOSA lens instead uses the selected actual annual series;
the GED-only reference index is disabled there. Annual labels remain years, not
invented January 1 measurement dates.

## Export and verification

`policy-research-selection/1` remains a separate format from both the semantic
catalogue and native TACITUS knowledge contexts. Download at most 200 records and
1 MiB, with matched/exported/omitted counts, dataset attribution and separate
analyst notes. Database exports identify the backend, snapshot and current page;
selected reference-index records identify their own country and dates. Annual
exports never claim event/actor/precision filters were applied to their values.

The maintained browser entry points are `testObservations(page, baseURL)` in
`tests/observations-browser.js` and `testObservationsDatabase(page, baseURL)` in
`tests/observations-database-browser.js`. The first runs against the generated
static build. The second requires an explicitly enabled, same-origin, real
read-only API and tests its pagination, original fields, source labels, export
receipts and terminal failure behavior. Its deliberate HTTP 503 interception is
a test outage, not production availability evidence. Local SQLite validation is
not a deployed Cloudflare D1 acceptance result.
