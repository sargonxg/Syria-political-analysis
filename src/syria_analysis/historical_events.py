"""Pinned, historical UCDP GED ingestion and verified static assets.

No API keys, current-event polling, inferred affiliations or model calls.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import html
import io
import json
import math
import re
import sqlite3
import tempfile
import unicodedata
import urllib.parse
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

DATASET_ID = "ucdp-ged-26.1"
VERSION = "26.1"
SNAPSHOT_FORMAT = "ucdp-ged-historical-snapshot/1"
SNAPSHOT_DIRECTORY = Path("data/historical") / DATASET_ID
ARCHIVE_URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
ARCHIVE_SHA256 = "8c941d84954e555ee2e54f40fa04d9203bf1e2f962203d0a9930966c4947c667"
ARCHIVE_BYTES = 39122522
CSV_MEMBER = "GEDEvent_v26_1.csv"
CSV_SHA256 = "61c3bf0a86374778343ba30c28a18b1fe739e2c33a76055504427eded4f8be27"
CSV_BYTES = 273992720
CODEBOOK_URL = "https://ucdp.uu.se/downloads/ged/ged261.pdf"
CODEBOOK_SHA256 = "f767380ebbf365aec7586f98b6d100cafb69fb54010a908604d53bd9ad655972"
COLLECTION_URL = "https://ucdp.uu.se/downloads/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
MAX_SHARD_BYTES = 1536 * 1024
START_YEAR, END_YEAR = 2000, 2025
COUNTRIES = {
    "Syria": "SY",
    "Iraq": "IQ",
    "Lebanon": "LB",
    "Israel": "IL",
    "Jordan": "JO",
    "Egypt": "EG",
    "Yemen (North Yemen)": "YE",
    "Iran": "IR",
    "Turkey": "TR",
}
COLUMNS = (
    "id",
    "relid",
    "year",
    "active_year",
    "code_status",
    "type_of_violence",
    "conflict_dset_id",
    "conflict_new_id",
    "conflict_name",
    "dyad_dset_id",
    "dyad_new_id",
    "dyad_name",
    "side_a_dset_id",
    "side_a_new_id",
    "side_a",
    "side_b_dset_id",
    "side_b_new_id",
    "side_b",
    "number_of_sources",
    "source_article",
    "source_office",
    "source_date",
    "source_headline",
    "source_original",
    "where_prec",
    "where_coordinates",
    "where_description",
    "adm_1",
    "adm_2",
    "latitude",
    "longitude",
    "geom_wkt",
    "priogrid_gid",
    "country",
    "country_id",
    "region",
    "event_clarity",
    "date_prec",
    "date_start",
    "date_end",
    "deaths_a",
    "deaths_b",
    "deaths_civilians",
    "deaths_unknown",
    "best",
    "high",
    "low",
    "gwnoa",
    "gwnob",
)
COMPACT_COLUMNS = (
    "year",
    "type_of_violence",
    "side_a",
    "side_b",
    "side_a_new_id",
    "side_b_new_id",
    "best",
    "low",
    "high",
    "where_prec",
    "date_prec",
    "event_clarity",
    "adm_1",
    "adm_2",
    "where_coordinates",
)
# Publication-scope filtering removes whole records, never words within evidence.
# This pattern is pipeline code only and is never copied into the static bundle.
_EXCLUDED = re.compile(
    r"\b(?:u\.?a\.?e\.?|united[\W_]*arab[\W_]*emirates|emirati(?:s)?|"
    r"abu[\W_]*dhabi|dubai)\b",
    re.IGNORECASE,
)
PRECISION = {
    "where_prec": {
        "1": "Exact named location",
        "2": "Within 25 km of a known point",
        "3": "Second-order administrative area representative point",
        "4": "First-order administrative area representative point",
        "5": "Linear feature or informal area representative point",
        "6": "Country-level location",
        "7": "Estimated location at sea or in the air",
    },
    "date_prec": {
        "1": "Exact day",
        "2": "Two-to-six-day range",
        "3": "Week",
        "4": "Eight-to-thirty-day range or month",
        "5": "Longer than a month, within a calendar year",
    },
    "event_clarity": {
        "1": "Individually identifiable event",
        "2": "Aggregate reporting not fully disaggregated",
    },
    "type_of_violence": {
        "1": "State-based conflict",
        "2": "Non-state conflict",
        "3": "One-sided violence",
    },
}
LIMITATIONS = [
    f"Historical coded observations, {START_YEAR}–{END_YEAR}; not a current operational feed.",
    "A selected-country subset, not complete violence, news or policy coverage.",
    "Provider country labels and coordinates are retained; lookup codes do not assert political boundaries or legal status.",
    "The provider Israel category contains location records in Gaza and the West Bank; no separate country series is invented.",
    "A coordinate can represent an administrative area, broad feature, country or estimated sea/air location; inspect where_prec.",
    "Date windows and date_prec are preserved; midnight strings in the raw source are not precise event timestamps.",
    "Low, best and high are provider estimates, not confidence intervals. Aggregate reporting can yield nonordered estimates; values are not repaired.",
    "Clear is the provider coding status, not a human review or a guarantee of truth.",
    "Source references are bibliographic metadata. Original news articles and private evidence are not bundled.",
    "Some whole records are omitted by publication scope; absence is not evidence of no violence.",
]


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def excluded_text(value: str) -> bool:
    """Check a decoded view; never mutate the original provider field."""
    if not value:
        return False
    text = unicodedata.normalize("NFKC", html.unescape(value))
    return bool(_EXCLUDED.search(urllib.parse.unquote(text)))


def raw_record_sha256(attributes: dict) -> str:
    """Digest exact string field values in sorted-key UTF-8 JSON."""
    return hashlib.sha256(_json_bytes(attributes)).hexdigest()


def _day(value: str) -> str:
    return date.fromisoformat(value.split(" ", 1)[0]).isoformat()


def _integer(row: dict, key: str) -> int:
    value = int(row[key])
    if str(value) != row[key]:
        raise ValueError(f"Noncanonical provider integer: {key}")
    return value


def normalize_record(row: dict) -> dict:
    """Retain all 49 fields; normalize only additional display/index fields."""
    if set(row) != set(COLUMNS) or any(not isinstance(v, str) for v in row.values()):
        raise ValueError("Expected exactly 49 original string fields")
    if any(excluded_text(value) for value in row.values()):
        raise ValueError("Record is outside publication scope")
    provider_id = row["id"]
    if not re.fullmatch(r"[0-9]+", provider_id):
        raise ValueError("A numeric provider event id is required")
    if row["country"] not in COUNTRIES:
        raise ValueError("Country is outside the curated historical scope")
    year = _integer(row, "year")
    if not START_YEAR <= year <= END_YEAR:
        raise ValueError("Year is outside the frozen historical window")
    start, end = _day(row["date_start"]), _day(row["date_end"])
    if start > end:
        raise ValueError("Provider date window is reversed")
    latitude, longitude = float(row["latitude"]), float(row["longitude"])
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError("Provider coordinates are not valid")
    for key, values in PRECISION.items():
        if row[key] not in values:
            raise ValueError(f"Unknown provider precision/category code: {key}")
    estimates = [_integer(row, key) for key in ("low", "best", "high")]
    for key in ("deaths_a", "deaths_b", "deaths_civilians", "deaths_unknown"):
        if _integer(row, key) < 0:
            raise ValueError("Negative provider fatality component")
    flags = []
    if not estimates[0] <= estimates[1] <= estimates[2]:
        flags.append("provider_estimates_not_ordered")
    if row["event_clarity"] == "2":
        flags.append("aggregate_reporting")
    return {
        "id": f"ucdp-ged:{VERSION}:{provider_id}",
        "provider_id": provider_id,
        "kind": "conflict_event",
        "dataset_id": DATASET_ID,
        "country_code": COUNTRIES[row["country"]],
        "country": row["country"],
        "label": f"{row['where_coordinates']} · {start}",
        "date_start": start,
        "date_end": end,
        "latitude": latitude,
        "longitude": longitude,
        "source_locator": f"{CSV_MEMBER}; id={provider_id}",
        "raw_record_sha256": raw_record_sha256(row),
        "quality_flags": flags,
        "attributes": dict(row),
    }


def _dataset_metadata() -> dict:
    return {
        "id": DATASET_ID,
        "kind": "conflict_event",
        "title": "UCDP GED · selected Middle East history",
        "version": VERSION,
        "publisher": "Uppsala Conflict Data Program, Uppsala University",
        "url": COLLECTION_URL,
        "license": "CC BY 4.0",
        "license_url": LICENSE_URL,
        "sha256": ARCHIVE_SHA256,
        "archive_url": ARCHIVE_URL,
        "archive_bytes": ARCHIVE_BYTES,
        "csv_member": CSV_MEMBER,
        "csv_sha256": CSV_SHA256,
        "csv_bytes": CSV_BYTES,
        "codebook_url": CODEBOOK_URL,
        "codebook_sha256": CODEBOOK_SHA256,
        "coverage": {
            "date_start": f"{START_YEAR}-01-01",
            "date_end": f"{END_YEAR}-12-31",
        },
        "precision": PRECISION,
        "limitations": LIMITATIONS,
        "attribution": [
            "UCDP GED Global version 26.1, Uppsala University.",
            "Davies, Pettersson and Öberg (2026), Organized violence 1989–2025, and violent political protests. https://doi.org/10.1093/jopres/xjag046",
            "Sundberg and Melander (2013), Introducing the UCDP Georeferenced Event Dataset. Journal of Peace Research 50(4), 523–532.",
            "Högbladh (2026), UCDP GED Codebook version 26.1.",
            "Modified distribution: selected countries and provider years, whole-record scope filtering, normalized index fields and deterministic sharding. Original retained field values are unchanged. No provider endorsement is implied.",
        ],
    }


_PART_PREFIX, _PART_SUFFIX = b'{"records":[', b"]}\n"
_PART_OVERHEAD = len(_PART_PREFIX) + len(_PART_SUFFIX)


def _new_part(country_code: str, year: int, number: int) -> dict:
    if number > 999:
        raise ValueError("Too many parts for one country/year")
    return {
        "country_code": country_code,
        "year": year,
        "number": number,
        "raw_path": f"./data/events-raw/{country_code}/{year}-{number:03}.json",
        "raw": [],
        "compact": [],
        "raw_size": 0,
        "compact_size": 0,
        "start": None,
        "end": None,
    }


def _encoded_pair(record: dict, raw_path: str) -> tuple[bytes, bytes]:
    full = {**record, "raw_shard": raw_path}
    compact = {
        **full,
        "attributes": {key: record["attributes"][key] for key in COMPACT_COLUMNS},
    }
    return _json_bytes(compact), _json_bytes(full)


def _flush_part(staging: Path, part: dict, max_shard_bytes: int) -> tuple[dict, dict]:
    if not part["raw"]:
        raise ValueError("An empty historical part cannot be written")
    common = {
        "dataset_id": DATASET_ID,
        "country_code": part["country_code"],
        "year_start": int(part["start"][:4]),
        "year_end": int(part["end"][:4]),
        "partition_year": part["year"],
        "part": part["number"],
        "count": len(part["raw"]),
        "date_start": part["start"],
        "date_end": part["end"],
    }
    entries = []
    for directory, records in [
        ("events", part["compact"]),
        ("events-raw", part["raw"]),
    ]:
        relative = f"{directory}/{part['country_code']}/{part['year']}-{part['number']:03}.json"
        body = _PART_PREFIX + b",".join(records) + _PART_SUFFIX
        if len(body) > max_shard_bytes:
            raise ValueError("Shard exceeds its byte budget")
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        entries.append(
            {
                **common,
                "path": "./data/" + relative,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    return entries[0], entries[1]


def _write_snapshot(
    rows, output: Path, *, built_at: str, max_shard_bytes: int = MAX_SHARD_BYTES
) -> dict:
    """Stream records through a temporary SQLite spool, not an in-memory corpus."""
    output = output.resolve()
    if output.exists():
        raise ValueError(
            "Snapshot output must be new; existing data is not overwritten"
        )
    if not 1024 <= max_shard_bytes <= MAX_SHARD_BYTES:
        raise ValueError("Shard bound must be between 1024 and 1572864 bytes")
    output.parent.mkdir(parents=True, exist_ok=True)
    totals, country_counts, flags = Counter(), Counter(), Counter()
    precisions = {name: Counter() for name in PRECISION}
    bounds = {}
    with tempfile.TemporaryDirectory(
        prefix=".ucdp-ged-", dir=output.parent
    ) as temporary:
        staging = Path(temporary) / "snapshot"
        staging.mkdir()
        database = sqlite3.connect(Path(temporary) / "spool.sqlite3")
        try:
            database.execute(
                "CREATE TABLE events (provider_id INTEGER PRIMARY KEY, country TEXT, year INTEGER, record BLOB)"
            )
            for row in rows:
                totals["source_rows"] += 1
                if set(row) != set(COLUMNS):
                    raise ValueError("Provider CSV columns changed")
                if (
                    row["country"] not in COUNTRIES
                    or not START_YEAR <= int(row["year"]) <= END_YEAR
                ):
                    continue
                totals["scope_candidates"] += 1
                if any(excluded_text(value) for value in row.values()):
                    totals["excluded_whole_records"] += 1
                    continue
                record = normalize_record(row)
                try:
                    database.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?)",
                        (
                            int(row["id"]),
                            record["country_code"],
                            int(row["year"]),
                            _json_bytes(record),
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Duplicate provider event id") from exc
                totals["retained_records"] += 1
                country_counts[record["country_code"]] += 1
                flags.update(record["quality_flags"])
                for name, counts in precisions.items():
                    counts[row[name]] += 1
                x, y = record["longitude"], record["latitude"]
                prior = bounds.setdefault(record["country_code"], [x, y, x, y])
                prior[:] = [
                    min(prior[0], x),
                    min(prior[1], y),
                    max(prior[2], x),
                    max(prior[3], y),
                ]
            database.commit()
            if not totals["retained_records"]:
                raise ValueError("No real records remain in the requested scope")
            event_shards, raw_shards = [], []
            for country_code in COUNTRIES.values():
                years = [
                    r[0]
                    for r in database.execute(
                        "SELECT DISTINCT year FROM events WHERE country=? ORDER BY year",
                        (country_code,),
                    )
                ]
                for year in years:
                    part = _new_part(country_code, year, 1)
                    for (body,) in database.execute(
                        "SELECT record FROM events WHERE country=? AND year=? ORDER BY provider_id",
                        (country_code, year),
                    ):
                        record = json.loads(body)
                        compact, full = _encoded_pair(record, part["raw_path"])
                        raw_size = (
                            _PART_OVERHEAD
                            + part["raw_size"]
                            + len(full)
                            + len(part["raw"])
                        )
                        compact_size = (
                            _PART_OVERHEAD
                            + part["compact_size"]
                            + len(compact)
                            + len(part["compact"])
                        )
                        if (
                            part["raw"]
                            and max(raw_size, compact_size) > max_shard_bytes
                        ):
                            compact_entry, raw_entry = _flush_part(
                                staging, part, max_shard_bytes
                            )
                            event_shards.append(compact_entry)
                            raw_shards.append(raw_entry)
                            part = _new_part(country_code, year, part["number"] + 1)
                            compact, full = _encoded_pair(record, part["raw_path"])
                        if (
                            max(len(compact), len(full)) + _PART_OVERHEAD
                            > max_shard_bytes
                        ):
                            raise ValueError(
                                "One provider record exceeds the shard bound"
                            )
                        part["compact"].append(compact)
                        part["raw"].append(full)
                        part["compact_size"] += len(compact)
                        part["raw_size"] += len(full)
                        part["start"] = min(
                            part["start"] or record["date_start"], record["date_start"]
                        )
                        part["end"] = max(
                            part["end"] or record["date_end"], record["date_end"]
                        )
                    compact_entry, raw_entry = _flush_part(
                        staging, part, max_shard_bytes
                    )
                    event_shards.append(compact_entry)
                    raw_shards.append(raw_entry)
            manifest = {
                "format": SNAPSHOT_FORMAT,
                "built_at": built_at,
                "datasets": [_dataset_metadata()],
                "countries": [
                    {
                        "code": code,
                        "name": name,
                        "event_count": country_counts[code],
                        "bbox": bounds[code],
                    }
                    for name, code in COUNTRIES.items()
                    if country_counts[code]
                ],
                "event_shards": event_shards,
                "raw_shards": raw_shards,
                "indicator_shards": [],
                "limitations": LIMITATIONS,
                "selection": {
                    "provider_year_start": START_YEAR,
                    "provider_year_end": END_YEAR,
                    "country_codes": list(COUNTRIES.values()),
                    **dict(totals),
                    "omission_policy": "Whole-record publication-scope filter; no retained field is redacted.",
                    "retained_fields_modified": False,
                },
                "quality_flag_counts": dict(flags),
                "precision_counts": {k: dict(v) for k, v in precisions.items()},
                "source_columns": list(COLUMNS),
                "raw_hash_serialization": "SHA-256 of sorted-key, compact UTF-8 JSON of all49 original string fields; ensure_ascii=False.",
                "max_shard_bytes": max_shard_bytes,
            }
            (staging / "manifest.json").write_bytes(_json_bytes(manifest) + b"\n")
        finally:
            database.close()
        staging.rename(output)
    return manifest


def create_snapshot(archive: Path, output: Path) -> dict:
    """Verify the official pinned archive and build a finite immutable snapshot."""
    if archive.stat().st_size != ARCHIVE_BYTES or _sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("Archive does not match the pinned official GED26.1 download")
    csv.field_size_limit(50 * 1024 * 1024)
    with zipfile.ZipFile(archive) as package:
        member = package.getinfo(CSV_MEMBER)
        if member.file_size != CSV_BYTES:
            raise ValueError("Pinned CSV member size differs")
        digest = hashlib.sha256()
        with package.open(member) as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != CSV_SHA256:
            raise ValueError("Pinned CSV member digest differs")
        with package.open(member) as stream:
            reader = csv.DictReader(
                io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            )
            if reader.fieldnames != list(COLUMNS):
                raise ValueError("Official CSV header differs from the pinned contract")
            return _write_snapshot(
                reader,
                output,
                built_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )


def _snapshot_file(snapshot: Path, item: dict) -> Path:
    value = item.get("path", "")
    if not re.fullmatch(
        r"\./data/events(?:-raw)?/[A-Z]{2}/[0-9]{4}-[0-9]{3}\.json", value
    ):
        raise ValueError("Unexpected historical asset path")
    path = snapshot / value.removeprefix("./data/")
    if path.is_symlink() or not path.resolve().is_relative_to(snapshot.resolve()):
        raise ValueError("Historical asset must remain inside its snapshot")
    if not path.is_file() or path.stat().st_size != item["bytes"]:
        raise ValueError("Historical asset is absent or has a different size")
    if item["bytes"] > MAX_SHARD_BYTES or _sha256(path) != item["sha256"]:
        raise ValueError("Historical asset integrity check failed")
    return path


def validate_snapshot(snapshot: Path) -> dict:
    """Verify every committed shard and the exact raw/compact provenance joins."""
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != SNAPSHOT_FORMAT:
        raise ValueError("Unsupported historical snapshot")
    if (
        len(manifest.get("datasets", [])) != 1
        or manifest["datasets"][0]["id"] != DATASET_ID
    ):
        raise ValueError("Unexpected historical dataset")
    if manifest["datasets"][0] != _dataset_metadata():
        raise ValueError("Historical source metadata differs from the pinned release")
    raw_index = {item["path"]: item for item in manifest["raw_shards"]}
    if len(raw_index) != len(manifest["raw_shards"]):
        raise ValueError("Duplicate raw shard path")
    seen, flags, country_counts, count = set(), Counter(), Counter(), 0
    for item in manifest["event_shards"]:
        path = _snapshot_file(snapshot, item)
        raw_path = item["path"].replace("/events/", "/events-raw/")
        raw_item = raw_index.get(raw_path)
        if not raw_item:
            raise ValueError("A compact shard has no exact raw partner")
        raw_file = _snapshot_file(snapshot, raw_item)
        compact = json.loads(path.read_text(encoding="utf-8"))["records"]
        raw = json.loads(raw_file.read_text(encoding="utf-8"))["records"]
        if (
            len(compact) != item["count"]
            or len(raw) != raw_item["count"]
            or len(compact) != len(raw)
        ):
            raise ValueError("Historical shard record counts disagree")
        for point, full in zip(compact, raw, strict=True):
            if full["id"] in seen:
                raise ValueError("Duplicate event across historical shards")
            seen.add(full["id"])
            expected = normalize_record(full["attributes"])
            expected["raw_shard"] = raw_path
            if full != expected:
                raise ValueError(
                    "Raw event does not preserve its exact original fields"
                )
            expected["attributes"] = {
                key: full["attributes"][key] for key in COMPACT_COLUMNS
            }
            if point != expected or point["country_code"] != item["country_code"]:
                raise ValueError("Compact/raw record provenance differs")
            flags.update(point["quality_flags"])
            country_counts[point["country_code"]] += 1
            count += 1
    if len(raw_index) != len(manifest["event_shards"]):
        raise ValueError("Unexpected unpaired raw shards")
    if count != manifest["selection"]["retained_records"]:
        raise ValueError("Historical manifest total differs")
    if dict(flags) != manifest["quality_flag_counts"]:
        raise ValueError("Historical quality counts differ")
    if dict(country_counts) != {
        row["code"]: row["event_count"] for row in manifest["countries"]
    }:
        raise ValueError("Historical country totals differ")
    if excluded_text(json.dumps(manifest, ensure_ascii=False)):
        raise ValueError("Historical manifest is outside publication scope")
    return manifest


def build_static_bundle(repository: Path, output: Path) -> dict:
    """Publish compact JSON and deterministic gzip evidence, never source archives.

    The immutable input remains ordinary JSON. Served pairs are repartitioned only
    when their longer gzip references would exceed the decoded asset byte budget.
    """
    snapshot = repository / SNAPSHOT_DIRECTORY
    manifest = validate_snapshot(snapshot)
    event_shards, raw_shards = [], []

    def write_asset(path: str, body: bytes) -> None:
        destination = output / path.removeprefix("./")
        if not destination.resolve().is_relative_to(output.resolve()):
            raise ValueError("Static event path escapes the output directory")
        if destination.is_symlink():
            raise ValueError("Refusing a symbolic-link static event asset")
        if destination.exists():
            if _sha256(destination) != hashlib.sha256(body).hexdigest():
                raise ValueError("Refusing to overwrite a changed static event asset")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)

    def new_part(country_code: str, year: int, number: int) -> dict:
        part = _new_part(country_code, year, number)
        part["raw_path"] += ".gz"
        return part

    def publish_part(part: dict) -> None:
        if not part["raw"]:
            return
        compact_body = _PART_PREFIX + b",".join(part["compact"]) + _PART_SUFFIX
        raw_body = _PART_PREFIX + b",".join(part["raw"]) + _PART_SUFFIX
        if max(len(compact_body), len(raw_body)) > MAX_SHARD_BYTES:
            raise ValueError("Served historical part exceeds its decoded byte budget")
        compressed = io.BytesIO()
        # GzipFile gives a fixed OS header across Python platforms; gzip.compress
        # with mtime=0 can instead delegate an OS-specific header to zlib.
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=compressed, compresslevel=9, mtime=0
        ) as stream:
            stream.write(raw_body)
        raw_gzip = compressed.getvalue()
        if len(raw_gzip) > MAX_SHARD_BYTES:
            raise ValueError("Compressed historical part exceeds its byte budget")
        common = {
            "dataset_id": DATASET_ID,
            "country_code": part["country_code"],
            "year_start": int(part["start"][:4]),
            "year_end": int(part["end"][:4]),
            "partition_year": part["year"],
            "part": part["number"],
            "count": len(part["raw"]),
            "date_start": part["start"],
            "date_end": part["end"],
        }
        compact_path = part["raw_path"].replace("/events-raw/", "/events/")[:-3]
        # Do not leave a second, uncompressed full-record copy in an old build.
        legacy_raw = output / part["raw_path"].removeprefix("./")[:-3]
        if legacy_raw.exists() or legacy_raw.is_symlink():
            raise ValueError("Use a fresh static output: uncompressed evidence remains")
        write_asset(compact_path, compact_body)
        write_asset(part["raw_path"], raw_gzip)
        event_shards.append(
            {
                **common,
                "path": compact_path,
                "bytes": len(compact_body),
                "sha256": hashlib.sha256(compact_body).hexdigest(),
            }
        )
        raw_shards.append(
            {
                **common,
                "path": part["raw_path"],
                "encoding": "gzip",
                "bytes": len(raw_gzip),
                "sha256": hashlib.sha256(raw_gzip).hexdigest(),
                "decoded_bytes": len(raw_body),
                "decoded_sha256": hashlib.sha256(raw_body).hexdigest(),
            }
        )

    part = None
    for source_item in manifest["raw_shards"]:
        country_code, year = source_item["country_code"], source_item["partition_year"]
        if part is None or (part["country_code"], part["year"]) != (
            country_code,
            year,
        ):
            if part is not None:
                publish_part(part)
            part = new_part(country_code, year, 1)
        source = _snapshot_file(snapshot, source_item)
        for original in json.loads(source.read_text(encoding="utf-8"))["records"]:
            compact, full = _encoded_pair(original, part["raw_path"])
            sizes = (
                _PART_OVERHEAD + part["raw_size"] + len(full) + len(part["raw"]),
                _PART_OVERHEAD
                + part["compact_size"]
                + len(compact)
                + len(part["compact"]),
            )
            if part["raw"] and max(sizes) > MAX_SHARD_BYTES:
                publish_part(part)
                part = new_part(country_code, year, part["number"] + 1)
                compact, full = _encoded_pair(original, part["raw_path"])
            if max(len(compact), len(full)) + _PART_OVERHEAD > MAX_SHARD_BYTES:
                raise ValueError("One served historical record exceeds the byte budget")
            part["compact"].append(compact)
            part["raw"].append(full)
            part["compact_size"] += len(compact)
            part["raw_size"] += len(full)
            part["start"] = min(
                part["start"] or original["date_start"], original["date_start"]
            )
            part["end"] = max(part["end"] or original["date_end"], original["date_end"])
    if part is not None:
        publish_part(part)
    return {
        "format": "policy-observation-atlas/1",
        "built_at": manifest["built_at"],
        **{
            key: manifest[key]
            for key in (
                "datasets",
                "countries",
                "indicator_shards",
                "limitations",
                "quality_flag_counts",
                "precision_counts",
            )
        },
        "event_shards": event_shards,
        "raw_shards": raw_shards,
        "selection": manifest["selection"],
    }
