# What the research database stores

This profile was measured against the local, read-only v16 SQLite snapshot on
7 November 2026. No remote D1 scan or data import was performed. It describes
storage allocation, not unique knowledge volume or model size.

- Local SQLite file: **460,959,744 bytes** (about 461 decimal MB / 440 MiB).
- Cached imported D1 file size: **452,685,824 bytes** (about 453 decimal MB).
  D1's physical layout differs from the local build; this is not a fresh bill or
  account-wide storage measurement.
- 120,576 UCDP GED 26.1 organized-violence observations, covering 2000–2025.
- 15,272 non-null annual World Bank values, 55 source profiles, five semantic
  lenses, four source manifests and their chunk-level provenance.
- Every event retains all 49 original provider fields alongside indexed columns.
  Full news articles, a trained AI model, embeddings, private notes and personal
  contact lists are not contained in this research snapshot.

## Local allocation

| Component | Allocated bytes |
| --- | ---: |
| Event table | 389,345,280 |
| Annual indicator table | 31,223,808 |
| All indexes | 39,350,272 |
| Source profiles | 499,712 |
| Manifest chunks | 483,328 |
| Other metadata/schema tables | 57,344 |

The event table includes 228,336,982 bytes of retained provider JSON, averaging
1,894 bytes per row. Its citation field accounts for 14,568,124 of those bytes.
Repeated JSON keys, repeated source wording and duplicated normalized/indexed
fields account for substantial storage beyond unique facts.

`dbstat` also reports **149,574,739 unused bytes inside allocated pages**, about
32.4% of the local file. These bytes are already included in the table/index
figures above; they are not another 150 MB on top. Variable-length row layout
can leave partially filled pages. A VACUUM alone is not a measured or guaranteed
solution to this packing overhead.

A future storage migration could dictionary-encode repeated values, keep a
compressed exact-provider archive and index a narrower projection. It must
preserve original fields, source identities and query behavior and should be
benchmarked before replacing the current snapshot. No database was rewritten,
shrunk or reimported for this profile.

## What a visitor downloads

The private personal preview uses static assets only. It does not download or
query this whole database. Compact country/year map partitions load first;
verified, compressed original fields load when requested. The new policy-document
example is a separate small curated selection. Its JSON byte counter measures
its own export, not the conflict corpus or model-token usage.

The detailed machine-readable measurement receipt is retained outside the
repository in `/workspace/research/site-refinement-20261107/database-size.json`.
Research snapshot identity:
`9d1f965e9abbeb9eb86e7eb36cdafca20cf453309ec0b2d879a41b48963a8369`.
