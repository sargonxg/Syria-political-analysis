#!/usr/bin/env python3
"""Split a frozen, valid research SQL dump into resumable bounded D1 imports.

This command is entirely local. It never uploads, contacts D1 or rewrites the
source. Original UTF-8 SQL bytes and statement order are retained in the parts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path

FORMAT = "policy-research-d1-import-parts/1"
MAX_PART_BYTES = 8 * 1024 * 1024
MAX_STATEMENT_BYTES = 95_000
CHECKPOINT_TABLE = "research_import_parts"
_HEADER = b"""-- Operator-only import checkpoints; original source SQL follows unchanged.
CREATE TABLE research_import_parts (
  part_number INTEGER PRIMARY KEY CHECK (part_number > 0),
  source_sql_sha256 TEXT NOT NULL CHECK (length(source_sql_sha256) = 64),
  source_payload_sha256 TEXT NOT NULL CHECK (length(source_payload_sha256) = 64),
  source_start INTEGER NOT NULL CHECK (source_start >= 0),
  source_bytes INTEGER NOT NULL CHECK (source_bytes > 0),
  source_statements INTEGER NOT NULL CHECK (source_statements > 0),
  prior_parts INTEGER NOT NULL CHECK (prior_parts = part_number - 1)
);
"""
_READY = re.compile(
    r"\s*INSERT\s+INTO\s+\"?research_meta\"?\s+VALUES\s*"
    r"\(\s*'state'\s*,\s*'\"ready\"'\s*\)\s*;\s*\Z",
    re.IGNORECASE,
)
_TRIVIA = re.compile(r"(?:\s+|--[^\r\n]*(?:\r?\n|$)|/\*[\s\S]*?\*/)*\Z")
_TRANSACTION = re.compile(
    r"\s*(?:--[^\r\n]*(?:\r?\n|$)|/\*[\s\S]*?\*/|\s)*"
    r"(?:BEGIN|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE)\b",
    re.IGNORECASE,
)


def hashes(body: bytes) -> dict:
    md5 = hashlib.md5(body, usedforsecurity=False).digest()
    return {
        "sha256": hashlib.sha256(body).hexdigest(),
        "md5": md5.hex(),
        "md5_base64": base64.b64encode(md5).decode("ascii"),
    }


def file_hashes(path: Path) -> dict:
    sha256, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as stream:
        for body in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(body)
            sha256.update(body)
            md5.update(body)
    return {
        "bytes": size,
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
        "md5_base64": base64.b64encode(md5.digest()).decode("ascii"),
    }


def sql_units(path: Path):
    """Yield exact complete statements, then optional trailing whitespace/comments.

    Candidate semicolons are checked by SQLite, including quoted semicolons,
    multiline strings/comments, CREATE statements and trigger bodies. Splitting
    by lines or by a plain semicolon delimiter would corrupt those statements.
    """
    pending, position = "", 0
    with path.open("r", encoding="utf-8", newline="") as stream:
        for block in iter(lambda: stream.read(64 * 1024), ""):
            pending += block
            while (semicolon := pending.find(";", position)) >= 0:
                position = semicolon + 1
                candidate = pending[:position]
                if sqlite3.complete_statement(candidate):
                    body = candidate.encode("utf-8")
                    if len(body) > MAX_STATEMENT_BYTES:
                        raise ValueError(
                            "Source statement exceeds the 95,000-byte D1 safety bound"
                        )
                    if _TRANSACTION.match(candidate):
                        raise ValueError(
                            "Source transaction wrappers cannot span independently imported parts"
                        )
                    yield body, True
                    pending, position = pending[position:], 0
            if len(pending.encode("utf-8")) > MAX_STATEMENT_BYTES:
                raise ValueError(
                    "Source statement or trailing text exceeds its read bound"
                )
    if pending:
        if not _TRIVIA.fullmatch(pending):
            raise ValueError("Source ends with incomplete or unterminated SQL")
        yield pending.encode("utf-8"), False


def checkpoint(
    sequence: int,
    source_sha256: str,
    payload_sha256: str,
    start: int,
    size: int,
    statements: int,
) -> bytes:
    return (
        "\n-- Commit this checkpoint only with its complete D1 import transaction.\n"
        "INSERT INTO research_import_parts VALUES ("
        f"{sequence},'{source_sha256}','{payload_sha256}',{start},{size},{statements},"
        f"(SELECT COUNT(*) FROM research_import_parts WHERE source_sql_sha256='{source_sha256}'));\n"
    ).encode("ascii")


def split_import(
    source: Path,
    output: Path,
    *,
    max_bytes: int = MAX_PART_BYTES,
    expected_sha256: str | None = None,
) -> dict:
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(
            "Use a fresh output directory; existing parts are never overwritten"
        )
    if not 1024 <= max_bytes <= MAX_PART_BYTES:
        raise ValueError("Part bound must be between 1,024 bytes and 8 MiB")
    identity = file_hashes(source)
    if expected_sha256 is not None and identity["sha256"] != expected_sha256:
        raise ValueError("Source SQL SHA-256 does not match the pinned import")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".d1-import-", dir=output.parent
    ) as temporary:
        staging = Path(temporary) / "parts"
        staging.mkdir()
        parts, payloads = [], []
        start = size = statements = total_statements = 0
        source_digest = hashlib.sha256()

        def fits(body_size: int, statement_count: int) -> bool:
            number = len(parts) + 1
            header = _HEADER if number == 1 else b""
            footer = checkpoint(
                number, identity["sha256"], "0" * 64, start, body_size, statement_count
            )
            return len(header) + body_size + len(footer) <= max_bytes

        def flush(*, final_ready: bytes | None = None) -> None:
            nonlocal start, size, statements, payloads
            if not payloads:
                raise ValueError(
                    "A data import part cannot have an empty source payload"
                )
            number = len(parts) + 1
            payload = b"".join(payloads)
            payload_identity = hashes(payload)
            header = _HEADER if number == 1 else b""
            footer = checkpoint(
                number,
                identity["sha256"],
                payload_identity["sha256"],
                start,
                len(payload),
                statements,
            )
            if final_ready is None:
                body = header + payload + footer
                segments = [{"file_start": len(header), "bytes": len(payload)}]
            else:
                before = payload[: -len(final_ready)]
                body = header + before + footer + final_ready
                segments = [
                    {"file_start": len(header), "bytes": len(before)},
                    {
                        "file_start": len(header) + len(before) + len(footer),
                        "bytes": len(final_ready),
                    },
                ]
            if len(body) > max_bytes:
                raise ValueError("A complete import part exceeds its byte budget")
            filename = f"part-{number:04d}.sql"
            (staging / filename).write_bytes(body)
            parts.append(
                {
                    "sequence": number,
                    "path": filename,
                    "bytes": len(body),
                    **hashes(body),
                    "source_payload": {
                        "start": start,
                        "end": start + len(payload),
                        "bytes": len(payload),
                        "statements": statements,
                        **payload_identity,
                        "file_segments": segments,
                    },
                    "publishes_ready": final_ready is not None,
                }
            )
            source_digest.update(payload)
            start += len(payload)
            size, statements, payloads = 0, 0, []

        def append(body: bytes) -> None:
            nonlocal size, statements, total_statements
            if payloads and not fits(size + len(body), statements + 1):
                flush()
            if not fits(len(body), 1) and not payloads:
                raise ValueError(
                    "One complete SQL statement plus checkpoint exceeds the requested part bound"
                )
            payloads.append(body)
            size += len(body)
            statements += 1
            total_statements += 1

        last, trailing = None, b""
        for body, is_statement in sql_units(source):
            if is_statement:
                if last is not None:
                    if _READY.fullmatch(last.decode("utf-8")):
                        raise ValueError(
                            "Source readiness marker must be its final SQL statement"
                        )
                    append(last)
                last = body
            else:
                trailing = body
        if last is None or not _READY.fullmatch(last.decode("utf-8")):
            raise ValueError("Source must end with the research_meta ready marker")
        final_ready = last + trailing
        append(final_ready)
        flush(final_ready=final_ready)
        if (
            start != identity["bytes"]
            or source_digest.hexdigest() != identity["sha256"]
        ):
            raise ValueError(
                "SQL changed during splitting or source bytes were not preserved"
            )
        manifest = {
            "format": FORMAT,
            "source_sql": {
                "name": source.name,
                **identity,
                "statements": total_statements,
            },
            "max_part_bytes": max_bytes,
            "part_count": len(parts),
            "checkpoint_table": CHECKPOINT_TABLE,
            "hash_basis": {
                "part": "Exact UTF-8 file bytes, including operator checkpoint SQL. SHA-256 is the integrity identity; MD5 is provided for upload transport.",
                "source_payload": "Exact contiguous byte range [start,end) from the untouched source SQL. Concatenate each part's file_segments in order to recover this range, excluding inserted operator SQL.",
                "checkpoint": "source_sql_sha256 identifies the entire original SQL; source_payload_sha256 identifies this part's exact original range, not the augmented part file.",
            },
            "resume": "Import in increasing sequence into a fresh database. After any interrupted call, query checkpoints and match every completed prefix row to this manifest before resuming. Do not replay committed parts.",
            "ready_policy": "Only the final part contains the original ready marker. Its checkpoint precedes that marker, which remains the last SQL statement. Use atomic D1 import transactions; readiness is never moved earlier.",
            "parts": parts,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.rename(output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-bytes", type=int, default=MAX_PART_BYTES)
    args = parser.parse_args()
    try:
        manifest = split_import(
            args.source,
            args.output,
            max_bytes=args.max_bytes,
            expected_sha256=args.expected_sha256,
        )
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "parts": manifest["part_count"],
                "source_bytes": manifest["source_sql"]["bytes"],
                "source_sha256": manifest["source_sql"]["sha256"],
                "maximum_part_bytes": max(part["bytes"] for part in manifest["parts"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
