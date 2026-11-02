# Sources and coverage

The register selects official reporting, international wires, Syrian/regional media, think tanks and individual analysts. It documents languages, subject remit, institutional self-description, useful coverage and known limits. These are editorial descriptions with linked evidence, not numerical credibility ratings or claims of political neutrality.

The initial corpus emphasizes primary UN documents on protection, reintegration, return estimates, selected services and the institutional political-process mandate. The nine map-linked paraphrases come from four primary reports or announcements. Other primary references support national or institutional context rather than points on the map.

## Actual connections

Two public RSS endpoints were verified and collected:

- Syria Direct: `https://syriadirect.org/feed/`
- Daraa 24: `https://daraa24.org/feed/`

Each initial collection is limited to six entries per endpoint. Only short titles, original URLs and feed dates are stored. The feed does not establish the underlying report's accuracy. A publisher present in the directory is not automatically a connected feed. Reuters, AP, AFP, think tanks and UN portals are reading sources here; no private API access is claimed.

Two social-account URLs are linked from official institutional profiles: Aron Lund's Century Foundation profile and Haid Haid's Chatham House profile. Their published legacy Twitter URLs are preserved. Automated access to the destination returned 403; no posts or active-account status were verified. Use an authorized API or supplied public material for any future content ingestion, with its own provenance and rights review. The current importer deliberately registers URLs only.

## Refresh and review

Run `syria-analysis collect-rss` explicitly, inspect the resulting changes, then rerun validation, tests and exports. No daemon or schedule runs by default. The GitHub manual workflow uploads an artifact for inspection and does not commit data.

To add a feed, confirm the public endpoint, record its verification date in the source registry and test the parsed record. Respect publisher terms and access controls. Do not guess endpoints, bypass a block, or treat a legacy integration as active.

Gaps remain substantial: the corpus is not an exhaustive event dataset; it does not capture all Syrian communities, Arabic-language debate, court records, economic indicators or daily policy changes. Its research questions are invitations to collect better evidence, not a substitute for doing so.
