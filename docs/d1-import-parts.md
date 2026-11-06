# Bounded, resumable D1 import

`scripts/split_d1_import.py` packages an already validated research SQL dump into
files no larger than **8 MiB**, including operator checkpoint statements. It does
not upload, execute remotely or modify the original dump. Use it when a large
single-file import is interrupted; a completed small part provides a verifiable
resume boundary.

```sh
python scripts/split_d1_import.py \
  --source output/v16/research-db/research.sql \
  --output output/v16/research-db-parts \
  --expected-sha256 4fc4933aa54ac43176e8dc2c61d34729241a02b3f7d1ca3fa028d8e0eb9a6201
```

That identity describes the frozen 286,806,509-byte v16 SQL file. The resulting
35 parts have a maximum size of 8,388,587 bytes. A different source dump needs its
own verified source hash and fresh output directory; existing parts are refused.
Keep SQL/database artifacts out of the static website package.

The splitter checks semicolon candidates with `sqlite3.complete_statement`,
preserving multiline definitions, quoted semicolons, escaped quotes, comments,
trigger bodies, Unicode and original line endings. No original statement or byte
is rewritten or reordered. Source statements must be terminated and within the
95,000-byte D1 safety bound. Explicit transaction wrappers are refused because
the import service must apply each part as its own atomic transaction.

## Manifest and checksum basis

`manifest.json` records the complete source identity and each part's sequence,
filename, byte count, SHA-256, MD5 hex and base64 MD5. SHA-256 is the integrity
identity; MD5 is supplied for upload protocols that require it.

Each part also has `source_payload`: the exact original byte range `[start,end)`,
its digests and statement count. `file_segments` identifies where those original
bytes appear inside the augmented part file. Concatenate those segments to recover
the range; concatenate the ranges in sequence to recover the original source
dump, including trailing whitespace/comments. The part-file hash includes the
inserted operator SQL; the source-payload hash excludes it.

## Operator sequence

1. Verify the original SQL identity against its build receipt. Use a fresh target
   research database for a new import. The splitter introduces only the independent
   `research_import_parts` table; existing research tables are never replaced.
2. Verify each part's exact file size and SHA-256 before upload. Files can be
   uploaded concurrently; **ingest them in increasing sequence**, one complete
   atomic D1 import transaction per file. Keep part files and their manifest frozen.
3. After success or an interrupted response, query the checkpoint table before
   deciding which file to import next:

   ```sql
   SELECT part_number, source_sql_sha256, source_payload_sha256,
          source_start, source_bytes, source_statements, prior_parts
   FROM research_import_parts
   ORDER BY part_number;
   ```

4. Match every returned row to the manifest's completed contiguous prefix. The
   full source hash, payload hash, range and statement count must agree. Resume at
   the next sequence; do not replay a committed part. If the failed transaction
   rolled back and no new checkpoint exists, retry that same next file.
5. Confirm the complete expected prefix and query `research_meta` only after the
   final part. The original `state="ready"` insert remains the **last SQL
   statement**, after all data, indexes and other metadata. The API's existing
   schema/format/snapshot readiness checks remain authoritative.

Each checkpoint stores `source_sql_sha256` for the entire original dump and
`source_payload_sha256` for that part's original range. A count constraint requires
the completed prefix for the same source. Replayed or skipped parts fail rather
than advancing the checkpoint. Atomic import transactions roll back their data and
checkpoint together; executing the statements individually does not provide this
guarantee. The final checkpoint is immediately before the original readiness
insert, so the marker is never published early.

If existing checkpoint rows differ from the manifest, stop that import and inspect
the target. Do not mix partitions from different source dumps or assume that an
upload response alone proves a transaction committed. No destructive reset is
performed by the splitter.

## Local verification

```sh
python -m unittest discover -s tests -p test_split_d1_import.py -v
python -m ruff check scripts/split_d1_import.py tests/test_split_d1_import.py
```

The tests replay all generated fixture parts and compare every original table
field and manifest value to the unsplit baseline. They also verify exact original
byte recovery, hashes/bounds, Unicode/multiline SQL, trigger bodies, readiness only
at the end, deterministic output and rollback on duplicate/out-of-order parts.
Missing readiness, incomplete SQL, incorrect source hashes, oversized statements
and preexisting output are refused.
