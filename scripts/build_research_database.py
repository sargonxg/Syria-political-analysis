#!/usr/bin/env python3
"""Build an offline SQLite database and bounded D1 SQL import; never contact a service."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

from syria_analysis import country_context
from syria_analysis import historical_events as ged
from syria_analysis.core import canonical_url
from syria_analysis.semantic_catalog import load_lenses

FORMAT = "policy-research-db/1"
SCHEMA_VERSION = 1
MAX_STATEMENT_BYTES = 95_000  # D1's documented per-statement limit is 100,000 bytes.
MAX_DATABASE_BYTES = 490_000_000
MANIFEST_CHUNK_BYTES = 24_000
ROOT = Path(__file__).resolve().parents[1]


def json_text(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def file_hash(path, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_chunks(text):
    """Preserve exact UTF-8 text while keeping even SQL-escaped literals bounded."""
    chunk, size = [], 0
    for char in text:
        length = len(char.encode("utf-8"))
        if chunk and size + length > MANIFEST_CHUNK_BYTES:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += length
    if chunk:
        yield "".join(chunk)


def add_manifest(connection, identifier, path, body):
    chunks = list(text_chunks(body.decode("utf-8")))
    connection.execute(
        "INSERT INTO manifests VALUES (?,?,?,?,?)",
        (identifier, path, sha256(body), len(body), len(chunks)),
    )
    connection.executemany(
        "INSERT INTO manifest_chunks VALUES (?,?,?)",
        ((identifier, i, text) for i, text in enumerate(chunks)),
    )


def add_dataset(connection, metadata):
    keys = ("id", "title", "version", "publisher", "url", "license", "sha256")
    connection.execute(
        "INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?)",
        (*[metadata[key] for key in keys], json_text(metadata)),
    )


def add_event(connection, record):
    attrs = record["attributes"]
    if len(attrs) != 49 or ged.raw_record_sha256(attrs) != record["raw_record_sha256"]:
        raise ValueError(
            "Original event attributes do not match their canonical provider digest"
        )
    actor_search = (attrs["side_a"] + "\n" + attrs["side_b"]).lower()
    values = (
        record["id"],
        record["dataset_id"],
        record["country_code"],
        int(attrs["year"]),
        record["date_start"],
        record["date_end"],
        int(attrs["type_of_violence"]),
        int(attrs["where_prec"]),
        int(attrs["date_prec"]),
        attrs["side_a"],
        attrs["side_b"],
        actor_search,
        record["latitude"],
        record["longitude"],
        int(attrs["low"]),
        int(attrs["best"]),
        int(attrs["high"]),
        record["raw_record_sha256"],
        json_text(record),
    )
    connection.execute(
        "INSERT INTO events VALUES (" + ",".join("?" for _ in values) + ")", values
    )


def sql_dump(connection, path):
    """One bounded statement per line; no DROP, remote transaction or ingestion command."""
    maximum = count = 0
    with path.open("wb") as stream:
        stream.write(
            b"-- Offline deterministic import for a NEW EMPTY research database.\nPRAGMA foreign_keys=ON;\n"
        )
        tables = (
            "schema_migrations",
            "research_meta",
            "datasets",
            "manifests",
            "manifest_chunks",
            "events",
            "indicators",
            "sources",
            "semantic_lenses",
        )

        def literal(value):
            if value is None:
                return "NULL"
            if isinstance(value, str):
                return "'" + value.replace("'", "''") + "'"
            if isinstance(value, bytes):
                return "X'" + value.hex() + "'"
            if type(value) in (int, float):
                return repr(value)
            raise ValueError("Unsupported SQL literal")

        def statements():
            for table in tables:
                row = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                yield row[0] + ";"
            # Parent manifests precede chunk rows. Readiness metadata is last,
            # after all data and indexes; D1 enforces foreign keys throughout.
            for table in (
                "schema_migrations",
                "datasets",
                "manifests",
                "manifest_chunks",
                "events",
                "indicators",
                "sources",
                "semantic_lenses",
            ):
                columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                keys = [
                    item[1]
                    for item in sorted(
                        (item for item in columns if item[5]), key=lambda item: item[5]
                    )
                ]
                order = ",".join('"' + key + '"' for key in keys)
                for values in connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY {order}'
                ):
                    yield (
                        f'INSERT INTO "{table}" VALUES('
                        + ",".join(literal(value) for value in values)
                        + ");"
                    )
            for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
            ):
                yield row[0] + ";"
            for values in connection.execute(
                "SELECT * FROM research_meta ORDER BY key"
            ):
                yield (
                    'INSERT INTO "research_meta" VALUES('
                    + ",".join(literal(value) for value in values)
                    + ");"
                )

        for statement in statements():
            body = (statement + "\n").encode("utf-8")
            if len(body) > MAX_STATEMENT_BYTES:
                raise ValueError("An SQL statement exceeds the bounded D1 import size")
            maximum = max(maximum, len(body))
            count += 1
            stream.write(body)
    return {"statements": count, "maximum_statement_bytes": maximum}


def build_database(repository, output, *, include_country_context=True):
    repository, output = Path(repository).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(
            "Use a fresh output directory; existing databases are never overwritten"
        )
    snapshot = repository / ged.SNAPSHOT_DIRECTORY
    event_manifest = ged.validate_snapshot(snapshot)
    source_file = repository / "data/sources/registry.json"
    sources_body = source_file.read_bytes()
    sources = json.loads(sources_body)
    if not isinstance(sources, list):
        raise TypeError("Source catalogue must be an array")
    lens_file = repository / "ontology/semantic-lenses.json"
    lens_body = lens_file.read_bytes() if lens_file.exists() else None
    lenses = load_lenses(repository)["lenses"] if lens_body is not None else []
    if not isinstance(lenses, list):
        raise TypeError("Semantic lenses must be an array")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".research-db-", dir=output.parent
    ) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        db_path = staging / "research.sqlite3"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.executescript(
                (ROOT / "cloudflare/schema.sql").read_text(encoding="utf-8")
            )
            manifests = {}
            counts, event_countries, annual_countries = Counter(), Counter(), Counter()
            country_names = {
                item["code"]: item["name"] for item in event_manifest["countries"]
            }
            event_body = (snapshot / "manifest.json").read_bytes()
            manifests["ucdp-ged-snapshot"] = sha256(event_body)
            add_manifest(
                connection,
                "ucdp-ged-snapshot",
                (ged.SNAPSHOT_DIRECTORY / "manifest.json").as_posix(),
                event_body,
            )
            for dataset in event_manifest["datasets"]:
                add_dataset(connection, dataset)
            for shard in event_manifest["raw_shards"]:
                rows = json.loads(
                    ged._snapshot_file(snapshot, shard).read_text(encoding="utf-8")
                )["records"]
                for row in rows:
                    add_event(connection, row)
                    counts["events"] += 1
                    event_countries[row["country_code"]] += 1
            if counts["events"] != event_manifest["selection"]["retained_records"]:
                raise ValueError("Research database lost historical event records")

            if include_country_context:
                # Reuse the verified, attributed normalized connector rather than
                # inventing a second interpretation of provider units/statuses.
                with tempfile.TemporaryDirectory(
                    prefix="country-context-", dir=Path(temporary)
                ) as annual_build:
                    fragment = country_context.build_static_bundle(
                        repository, Path(annual_build)
                    )
                    for dataset in fragment["datasets"]:
                        add_dataset(connection, dataset)
                    for country in fragment["countries"]:
                        country_names.setdefault(country["code"], country["name"])
                    for shard in fragment["indicator_shards"]:
                        body = (Path(annual_build) / shard["path"]).read_bytes()
                        if sha256(body) != shard["sha256"]:
                            raise ValueError(
                                "Generated country observation checksum differs"
                            )
                        rows = json.loads(body)["records"]
                        if len(rows) != shard["count"]:
                            raise ValueError(
                                "Generated country observation count differs"
                            )
                        for row in rows:
                            record = {
                                **row,
                                "kind": "country_indicator",
                                "label": f"{row['indicator_name']} · {row['year']}",
                                "date_start": f"{row['year']}-01-01",
                                "date_end": f"{row['year']}-12-31",
                            }
                            connection.execute(
                                "INSERT INTO indicators VALUES (?,?,?,?,?,?,?)",
                                (
                                    row["id"],
                                    row["dataset_id"],
                                    row["country_code"],
                                    row["indicator_code"],
                                    row["year"],
                                    row["value"],
                                    json_text(record),
                                ),
                            )
                            counts["indicators"] += 1
                            annual_countries[row["country_code"]] += 1
                annual_file = repository / "data/observations/world-bank/manifest.json"
                annual_body = annual_file.read_bytes()
                manifests["world-bank-snapshot"] = sha256(annual_body)
                add_manifest(
                    connection,
                    "world-bank-snapshot",
                    annual_file.relative_to(repository).as_posix(),
                    annual_body,
                )

            for profile in sorted(sources, key=lambda item: item["id"]):
                if not all(
                    isinstance(profile.get(key), str) and profile[key]
                    for key in ("id", "name", "type", "url")
                ):
                    raise ValueError("Source profiles require id, name, type and URL")
                canonical_url(profile["url"])
                if not profile.get("evidence"):
                    raise ValueError(
                        "Source profile has no attributed supporting evidence"
                    )
                encoded = json_text(profile)
                connection.execute(
                    "INSERT INTO sources VALUES (?,?,?,?,?,?)",
                    (
                        profile["id"],
                        profile["name"],
                        profile["type"],
                        profile["url"],
                        encoded.lower(),
                        encoded,
                    ),
                )
                counts["sources"] += 1
            manifests["source-catalogue"] = sha256(sources_body)
            add_manifest(
                connection,
                "source-catalogue",
                source_file.relative_to(repository).as_posix(),
                sources_body,
            )
            for lens in sorted(lenses, key=lambda item: item["id"]):
                connection.execute(
                    "INSERT INTO semantic_lenses VALUES (?,?,?,?)",
                    (lens["id"], lens["title"], lens["namespace"], json_text(lens)),
                )
                counts["lenses"] += 1
            if lens_body is not None:
                manifests["semantic-lenses"] = sha256(lens_body)
                add_manifest(
                    connection,
                    "semantic-lenses",
                    lens_file.relative_to(repository).as_posix(),
                    lens_body,
                )

            count_values = {
                key: counts[key]
                for key in ("events", "indicators", "sources", "lenses")
            }
            countries = [
                {
                    "code": code,
                    "name": country_names.get(code, code),
                    "events": event_countries[code],
                    "indicators": annual_countries[code],
                }
                for code in sorted(set(event_countries) | set(annual_countries))
            ]
            coverage = connection.execute(
                "SELECT min(date_start),max(date_end),min(event_year),max(event_year) FROM events"
            ).fetchone()
            snapshot_id = sha256(
                json_text(
                    {"schema_version": SCHEMA_VERSION, "manifests": manifests}
                ).encode()
            )
            metadata = {
                "format": FORMAT,
                "schema_version": SCHEMA_VERSION,
                "state": "ready",
                "snapshot": {
                    "id": snapshot_id,
                    "built_at": event_manifest["built_at"],
                    "date_start": coverage[0],
                    "date_end": coverage[1],
                    "from_year": coverage[2],
                    "to_year": coverage[3],
                    "manifests": manifests,
                },
                "counts": count_values,
                "countries": countries,
                "limitations": [
                    *event_manifest.get("limitations", []),
                    "Historical provider records; not a live feed, current territorial control or independently corroborated intelligence.",
                    "Country indicators are separate annual context; no event-to-indicator causal links are inferred.",
                    "Source-profile ownership and perspective statements retain their attributed evidence and limitations; no political bias score is inferred.",
                    "Semantic lenses are descriptive mappings to published vocabularies, not automated reasoning or entity equivalence assertions.",
                ],
            }
            connection.executemany(
                "INSERT INTO research_meta VALUES (?,?)",
                ((key, json_text(value)) for key, value in metadata.items()),
            )
            connection.commit()
            if (
                connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or connection.execute("PRAGMA foreign_key_check").fetchall()
            ):
                raise ValueError(
                    "Research database failed SQLite integrity/foreign-key validation"
                )
            details = sql_dump(connection, staging / "research.sql")
        finally:
            connection.close()
        if db_path.stat().st_size > MAX_DATABASE_BYTES:
            raise ValueError(
                "Research database exceeds its conservative 490 MB build budget"
            )
        receipt = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "counts": count_values,
            "database_bytes": db_path.stat().st_size,
            "database_sha256": file_hash(db_path),
            "sql_bytes": (staging / "research.sql").stat().st_size,
            "sql_sha256": file_hash(staging / "research.sql"),
            "sql_md5": file_hash(staging / "research.sql", "md5"),
            **details,
            "source_manifests": manifests,
            "automatic_ingestion": False,
            "read_only_http_api": True,
        }
        (staging / "build-receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New output directory; existing files are refused",
    )
    parser.add_argument(
        "--events-only",
        action="store_true",
        help="Omit annual country observations explicitly",
    )
    args = parser.parse_args()
    receipt = build_database(
        args.repository, args.output, include_country_context=not args.events_only
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
