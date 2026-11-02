# Data contract

All canonical tables are UTF-8 JSON arrays. IDs are stable within the repository. Document IDs are `doc-` followed by the first 16 hexadecimal characters of SHA-256 over the normalized source URL. Normalization removes fragments and common tracking parameters while preserving meaningful query parameters. Keep the original source URL when registering a new record; do not substitute a guessed headline URL.

| Table | Important fields | Relationships |
| --- | --- | --- |
| `sources` | `name`, `type`, `languages`, `scope`, `ownership_or_perspective`, `evidence`, `feeds` | Profile evidence is distinct from report evidence. |
| `documents` | `source_id`, `publisher`, `url`, `published_at`, `published_on`, `retrieved_at`, `retrieval_method`, `reporting_period`, `review_state` | `source_id` names the publishing body. |
| `claims` | `statement`, `evidence`, `place_ids`, `geographic_scope`, `qualification`, `review_state` | Evidence contains a document ID and locator. |
| `places` | `coordinates`, `coordinate_basis`, `precision`, `geographic_scope` | Coordinates are `[longitude, latitude]`, never reversed. |
| `context` | `record_type`, `summary`, `evidence`, `source_ids`, `scope`, `limits` | `source_ids` are suggested reading; evidence links carry support for the context record. |
| `social_accounts` | `source_id`, `url`, `profile_evidence_url`, `destination_status` | Verification is of the institutional profile link only. |
| `social_references` | `url`, `account_id`, `recorded_at`, `published_at`, `content_retrieved` | Post URL import is not content retrieval or verification. |

Record types for context are `institutional_context`, `dated_document_context` and `research_question`. A research question is a proposal, not a finding.

The [JSON schemas](../schemas) define record shapes. The Python validator additionally checks IDs, foreign keys, time-zone-aware timestamps, coordinate ranges, review-state boundaries and structural corroboration requirements. CI validates both. When extending the contract, update schemas, validation and meaningful failure tests together.

`exports/context.json` includes all tables, use rules and a typed evidence graph. The JSONL version begins with a manifest record, followed by one `{table, record}` object per canonical row. CSV tables JSON-encode nested fields and prefix spreadsheet-formula cells with an apostrophe; JSON retains the canonical value.

Collection refreshes unreviewed receipts by stable ID. A newly fetched title cannot overwrite a manually reviewed document. Collection failures are recorded by exception class without copying response bodies or proxy credentials into the data. A total feed failure returns a nonzero exit code and does not alter stored receipts.
