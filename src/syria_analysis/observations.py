"""Build and query the historical observation atlas from committed source snapshots."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import zlib
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .research_selection import make_selection

FORMAT = "policy-observation-atlas/1"


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_observation_atlas(repository: Path, output: Path):
    """No network collection or private cases occur during a static build."""
    from .country_context import build_static_bundle as context_bundle
    from .historical_events import build_static_bundle as events_bundle
    from .semantic_catalog import build_semantic_catalog

    repository, output = repository.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    web = Path(__file__).parent / "web"
    for source, target in (
        ("observations.html", "index.html"),
        ("observations.css", "observations.css"),
        ("observations.js", "observations.js"),
        ("observations-navigation.js", "observations-navigation.js"),
    ):
        shutil.copyfile(web / source, output / target)
    fragments = [events_bundle(repository, output), context_bundle(repository, output)]
    countries = {}
    for fragment in fragments:
        for country in fragment.get("countries", []):
            code = country["code"]
            countries[code] = {**countries.get(code, {}), **country}
    # Keep the event provider's geography name when the annual series uses another label.
    for country in fragments[0].get("countries", []):
        countries[country["code"]].update(country)
    manifest = {
        "format": FORMAT,
        "built_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "geography": "./data/land.json",
        "observation_ontology": "./data/observation-vocabulary.jsonld",
        "datasets": [d for f in fragments for d in f.get("datasets", [])],
        "countries": sorted(countries.values(), key=lambda c: c["code"]),
        "event_shards": fragments[0].get("event_shards", []),
        "raw_shards": fragments[0].get("raw_shards", []),
        "indicator_shards": fragments[1].get("indicator_shards", []),
        "limitations": list(
            dict.fromkeys(
                [
                    "Historical source records and annual country values have different units and coverage. They are not a causal model or a live risk forecast.",
                    "A mapped coordinate retains the provider's geographic precision. It is not proof of an exact incident location or current territorial control.",
                    "Provider geographic labels are retained as data classifications; this software makes no independent determination of borders or sovereignty.",
                    "The downloaded selection is bounded to 200 records and 1 MiB. Its matched and omitted counts remain explicit; full source partitions are separate files.",
                    *[v for f in fragments for v in f.get("limitations", [])],
                ]
            )
        ),
    }
    geography = repository / "data/observations/geography"
    shutil.copyfile(geography / "land.json", output / "data/land.json")
    shutil.copyfile(geography / "NOTICE.json", output / "data/geography-NOTICE.json")
    shutil.copyfile(
        repository / "schemas/research_selection.schema.json",
        output / "data/research-selection.schema.json",
    )
    shutil.copyfile(
        repository / "ontology/observations.jsonld",
        output / "data/observation-vocabulary.jsonld",
    )
    manifest["semantic_catalog"] = build_semantic_catalog(repository, output, manifest)
    _write(output / "data/manifest.json", manifest)
    return manifest


def _file(root, name):
    if not isinstance(name, str):
        # This reports malformed manifest data through the CLI's normal error path.
        raise ValueError("Shard path must be text")  # noqa: TRY004
    parsed = urlsplit(name)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or name.startswith("/")
    ):
        raise ValueError("Only local snapshot shard paths are allowed")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("Shard is outside this atlas or is missing")
    return target


def _load_shard(root, shard):
    payload = _file(root, shard["path"]).read_bytes()
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError("Shard exceeds the 2 MiB read boundary")
    if "bytes" in shard and (
        type(shard["bytes"]) is not int or len(payload) != shard["bytes"]
    ):
        raise ValueError("Snapshot shard byte count does not match its manifest")
    if hashlib.sha256(payload).hexdigest() != shard["sha256"]:
        raise ValueError("Snapshot shard checksum does not match: " + shard["path"])
    encoding = shard.get("encoding")
    if encoding == "gzip":
        decoded_bytes = shard.get("decoded_bytes")
        if type(decoded_bytes) is not int or not 0 <= decoded_bytes <= 2 * 1024 * 1024:
            raise ValueError("Decoded shard exceeds the 2 MiB boundary")
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as stream:
                decoded = stream.read(2 * 1024 * 1024 + 1)
        except (OSError, EOFError, zlib.error):
            raise ValueError("Snapshot raw shard is not valid gzip") from None
        if len(decoded) != decoded_bytes or len(decoded) > 2 * 1024 * 1024:
            raise ValueError("Decoded shard size does not match its manifest")
        if hashlib.sha256(decoded).hexdigest() != shard.get("decoded_sha256"):
            raise ValueError("Decoded shard checksum does not match its manifest")
        payload = decoded
    elif encoding not in (None, "identity"):
        raise ValueError("Unsupported snapshot shard encoding")
    data = json.loads(payload)
    rows = data if isinstance(data, list) else data["records"]
    if type(shard["count"]) is not int or len(rows) != shard["count"]:
        raise ValueError("Shard row count does not match its manifest")
    return rows


def query_observations(
    atlas,
    *,
    country="SY",
    from_year=2011,
    to_year=2025,
    actor="",
    violence_type=None,
    geography_precision=None,
    indicator=None,
    limit=200,
    question="",
    notes=None,
):
    """Filter attributed source rows, then hydrate only the exported bounded prefix."""
    atlas = Path(atlas).resolve()
    manifest = json.loads((atlas / "data/manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError("Unsupported observation-atlas manifest")
    if country not in {c["code"] for c in manifest["countries"]}:
        raise ValueError("Country is not present in this snapshot")
    if not 1900 <= from_year <= to_year <= 2100:
        raise ValueError("Provide an ordered historical year interval")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Selection limit must be between one and 200")
    if indicator and (
        actor or violence_type is not None or geography_precision is not None
    ):
        raise ValueError(
            "Actor, violence and geographic-precision filters do not apply to annual country values"
        )
    records = []
    shard_kind = "indicator_shards" if indicator else "event_shards"
    source_ids = set()
    for shard in manifest[shard_kind]:
        if shard["country_code"] != country:
            continue
        if not indicator and (
            shard["year_end"] < from_year or shard["year_start"] > to_year
        ):
            continue
        source_ids.add(shard["dataset_id"])
        for row in _load_shard(atlas, shard):
            if indicator:
                if (
                    row["indicator_code"] != indicator
                    or not from_year <= row["year"] <= to_year
                ):
                    continue
                item = dict(row)
                item.update(
                    kind="country_indicator",
                    label=f"{row['indicator_name']} · {row['year']}",
                    date_start=f"{row['year']}-01-01",
                    date_end=f"{row['year']}-12-31",
                )
            else:
                if (
                    row["date_end"] < f"{from_year}-01-01"
                    or row["date_start"] > f"{to_year}-12-31"
                ):
                    continue
                attrs = row["attributes"]
                if (
                    actor
                    and actor.casefold()
                    not in (
                        str(attrs.get("side_a", ""))
                        + " "
                        + str(attrs.get("side_b", ""))
                    ).casefold()
                ):
                    continue
                if violence_type is not None and str(
                    attrs.get("type_of_violence")
                ) != str(violence_type):
                    continue
                if geography_precision is not None and str(
                    attrs.get("where_prec")
                ) != str(geography_precision):
                    continue
                item = dict(row, kind="conflict_event")
            records.append(item)
    records.sort(key=lambda r: (r["date_start"], r["id"]))
    matched = len(records)
    prefix = records[:limit]
    raw_index = {r["path"]: r for r in manifest.get("raw_shards", [])}
    raw_cache = {}
    for i, row in enumerate(prefix):
        name = row.get("raw_shard")
        if not name:
            continue
        if name not in raw_index:
            raise ValueError("Raw source partition is absent from the manifest")
        if name not in raw_cache:
            raw_cache[name] = {r["id"]: r for r in _load_shard(atlas, raw_index[name])}
        original = raw_cache[name].get(row["id"])
        if not original or original.get("raw_record_sha256") != row.get(
            "raw_record_sha256"
        ):
            raise ValueError(
                "Raw source record identity does not match its point index"
            )
        from .historical_events import raw_record_sha256

        if raw_record_sha256(original["attributes"]) != row["raw_record_sha256"]:
            raise ValueError(
                "Original provider fields differ from their canonical record digest"
            )
        prefix[i] = dict(original, kind="conflict_event")
    datasets = [d for d in manifest["datasets"] if d["id"] in source_ids]
    if not datasets:
        raise ValueError("This country has no records for the requested source family")
    return make_selection(
        prefix,
        datasets,
        question=question,
        notes=notes,
        limit=limit,
        matched=matched,
        filters={
            "country_code": country,
            "from_year": from_year,
            "to_year": to_year,
            "actor": actor,
            "violence_type": violence_type,
            "geography_precision": geography_precision,
            "indicator_code": indicator,
        },
        limitations=manifest["limitations"][:30],
    )
