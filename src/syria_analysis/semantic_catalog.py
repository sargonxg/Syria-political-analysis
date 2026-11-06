"""Bounded, source-derived navigation across five explicitly scoped vocabularies.

The index is a navigation sample. Country/year descriptors reuse the atlas shards;
no second full event corpus, automatic political assertions or reasoner is built.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from . import historical_events as ged

FORMAT = "policy-semantic-catalog/1"
GRAPH_FORMAT = "policy-semantic-graph/1"
PARTITION_FORMAT = "policy-semantic-partition/1"
VERSION = "1.0.0"
RECORD_NODE_LIMIT = 2048
MAX_ASSET_BYTES = 3 * 1024 * 1024
LENS_IDS = ("prov-o", "skos", "owl-time", "geosparql", "sosa-ssn")
LIMITATIONS = [
    "Source-derived navigation and vocabulary alignment, not a reasoner or full standards compliance.",
    "Source records are unreviewed here; provenance and category links are not independent corroboration.",
    "No affiliation, control, causal relationship, credibility ranking or political conclusion is inferred.",
    "The graph overview is a bounded navigation sample, not a representative statistical sample or the whole corpus.",
    "The GED-only overview and World Bank annual example remain distinct source layers with different units and coverage.",
]


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not re.fullmatch(
        r"\./data/[A-Za-z0-9_./-]+\.json(?:\.gz)?", name
    ):
        raise ValueError("Semantic references must be local atlas JSON paths")
    relative = Path(name.removeprefix("./"))
    if ".." in relative.parts:
        raise ValueError("Semantic asset path must not traverse directories")
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Semantic asset escapes the atlas directory")
    return path


def _read(root: Path, descriptor: dict) -> dict:
    path = _path(root, descriptor["path"])
    if not path.is_file() or path.stat().st_size > MAX_ASSET_BYTES:
        raise ValueError("Semantic source asset is absent or exceeds its read bound")
    body = path.read_bytes()
    if (
        descriptor.get("bytes", len(body)) != len(body)
        or _digest(body) != descriptor["sha256"]
    ):
        raise ValueError("Semantic source asset checksum or size differs")
    data = json.loads(body)
    if "count" in descriptor and len(data["records"]) != descriptor["count"]:
        raise ValueError("Semantic source asset count differs")
    return data


def _write(root: Path, name: str, value: dict) -> dict:
    body = ged._json_bytes(value) + b"\n"
    if len(body) > MAX_ASSET_BYTES:
        raise ValueError("Semantic navigation asset exceeds its 3 MiB bound")
    if ged.excluded_text(body.decode("utf-8")):
        raise ValueError("Semantic navigation asset is outside publication scope")
    destination = _path(root, name)
    if destination.exists() and destination.read_bytes() != body:
        raise ValueError(
            "Refusing to overwrite a changed semantic asset; use a fresh build"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(body)
    return {"path": name, "bytes": len(body), "sha256": _digest(body)}


def load_lenses(repository: Path) -> dict:
    document = json.loads((repository / "ontology/semantic-lenses.json").read_bytes())
    if (
        document.get("format") != "policy-semantic-lenses/1"
        or document.get("version") != VERSION
    ):
        raise ValueError("Unsupported semantic lens definition")
    if tuple(item["id"] for item in document["lenses"]) != LENS_IDS:
        raise ValueError("The five scoped semantic lenses are required")
    context = document["context"]
    for lens in document["lenses"]:
        if not lens["scope"] or not lens["limitations"] or not lens["record_fields"]:
            raise ValueError(
                "A semantic lens must declare fields, scope and limitations"
            )
        for term in lens["terms"]:
            prefix, local = term["id"].split(":", 1)
            if term["url"] != context[prefix] + local:
                raise ValueError("A vocabulary term does not resolve to its namespace")
        for template in lens["templates"]:
            if template["predicate"].split(":", 1)[0] not in context:
                raise ValueError("Unknown semantic template predicate prefix")
    sosa = document["lenses"][-1]
    if sosa["applies_to"] != ["country_indicator"]:
        raise ValueError("SOSA examples must describe annual source observations")
    return document


def _concepts() -> list[dict]:
    return [
        {
            "id": "ucdp:type-of-violence:" + code,
            "kind": "concept",
            "label": label,
            "scheme": "ucdp:type-of-violence",
            "code": code,
        }
        for code, label in ged.PRECISION["type_of_violence"].items()
    ]


def _index_node(record: dict, shard: dict) -> dict:
    attributes = record["attributes"]
    code = attributes["type_of_violence"]
    if (
        record["dataset_id"] != ged.DATASET_ID
        or code not in ged.PRECISION["type_of_violence"]
    ):
        raise ValueError("Graph index requires a provider-coded GED record")
    if not re.fullmatch(r"[0-9a-f]{64}", record["raw_record_sha256"]):
        raise ValueError("A source record digest is required")
    return {
        **{
            key: record[key]
            for key in (
                "id",
                "kind",
                "dataset_id",
                "label",
                "country_code",
                "date_start",
                "date_end",
                "latitude",
                "longitude",
                "raw_shard",
                "raw_record_sha256",
            )
        },
        "compact_shard": shard["path"],
        "precision": {
            key: attributes[key] for key in ("where_prec", "date_prec", "event_clarity")
        },
        "concept": {
            "id": "ucdp:type-of-violence:" + code,
            "label": ged.PRECISION["type_of_violence"][code],
            "source_field": "type_of_violence",
            "value": code,
        },
    }


def _quotas(groups: dict, limit: int) -> dict:
    """Round-robin by nonempty country/year, without loading the whole corpus."""
    capacities = {
        key: sum(item["count"] for item in items) for key, items in groups.items()
    }
    quotas = dict.fromkeys(sorted(groups), 0)
    remaining = min(limit, sum(capacities.values()))
    while remaining:
        for key in quotas:
            if quotas[key] < capacities[key]:
                quotas[key] += 1
                remaining -= 1
                if not remaining:
                    break
    return quotas


def _annual_example(output: Path, manifest: dict, lenses: dict) -> dict | None:
    request = lenses["lenses"][-1]["example_request"]
    for shard in manifest.get("indicator_shards", []):
        if (
            shard["dataset_id"] != request["dataset_id"]
            or shard["country_code"] != "SY"
        ):
            continue
        for row in _read(output, shard)["records"]:
            if row["id"] != request["record_id"]:
                continue
            return {
                "lens": "sosa-ssn",
                "id": row["id"],
                "kind": "country_indicator",
                **{
                    key: row[key]
                    for key in (
                        "dataset_id",
                        "country_code",
                        "indicator_code",
                        "indicator_name",
                        "year",
                        "value",
                        "unit",
                        "source_locator",
                    )
                },
                "indicator_shard": shard["path"],
                "shard": {
                    **shard,
                    "bytes": _path(output, shard["path"]).stat().st_size,
                },
                "attributes_sha256": _digest(ged._json_bytes(row["attributes"])),
                "evidence_fields": {
                    field: row["attributes"][field.removeprefix("attributes.")]
                    for field in (
                        "attributes.countryiso3code",
                        "attributes.country_name",
                        "attributes.indicator_id",
                        "attributes.indicator_name",
                        "attributes.date",
                        "attributes.value",
                        "attributes.unit",
                    )
                },
                "qualification": "An annual provider population estimate. Display unit comes from series metadata; raw unit is retained separately. No physical sensor or exact measurement day is asserted.",
            }
    if manifest.get("indicator_shards"):
        raise ValueError("The declared real annual observation example is missing")
    return None


def build_semantic_catalog(
    repository: Path, output: Path, observation_manifest: dict
) -> dict:
    """Build after observation shards; return a descriptor for the atlas manifest."""
    repository, output = Path(repository).resolve(), Path(output).resolve()
    lenses = load_lenses(repository)
    snapshot_path = repository / ged.SNAPSHOT_DIRECTORY / "manifest.json"
    snapshot_body = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_body)
    source_sha256 = _digest(snapshot_body)
    if snapshot["datasets"][0] != ged._dataset_metadata():
        raise ValueError("Semantic source snapshot is not the pinned GED release")
    manifest = observation_manifest
    groups = defaultdict(list)
    for shard in manifest["event_shards"]:
        if shard["dataset_id"] != ged.DATASET_ID:
            raise ValueError("Unsupported event dataset in semantic catalog")
        groups[shard["country_code"], shard["partition_year"]].append(shard)
    total = sum(item["count"] for values in groups.values() for item in values)
    if total != snapshot["selection"]["retained_records"]:
        raise ValueError("Semantic partitions disagree with the immutable source count")
    raw_index = {item["path"]: item for item in manifest["raw_shards"]}
    quotas = _quotas(groups, RECORD_NODE_LIMIT)
    nodes, partitions, seen = [], [], set()
    for (country, year), shards in sorted(groups.items()):
        shards = sorted(shards, key=lambda item: item["part"])
        needed, partners = quotas[country, year], []
        for shard in shards:
            raw_path = shard["path"].replace("/events/", "/events-raw/") + ".gz"
            if (
                raw_path not in raw_index
                or raw_index[raw_path]["count"] != shard["count"]
            ):
                raise ValueError(
                    "Semantic partition lacks its registered evidence partner"
                )
            partners.append(raw_index[raw_path])
            if not needed:
                continue
            for row in _read(output, shard)["records"][:needed]:
                if row["raw_shard"] != raw_path or row["country_code"] != country:
                    raise ValueError("Semantic record has a mismatched source locator")
                if row["id"] in seen:
                    raise ValueError("Duplicate graph overview record")
                seen.add(row["id"])
                nodes.append(_index_node(row, shard))
                needed -= 1
        if needed:
            raise ValueError(
                "Semantic navigation quota exceeds available source records"
            )
        count = sum(shard["count"] for shard in shards)
        partition = {
            "format": PARTITION_FORMAT,
            "country_code": country,
            "partition_year": year,
            "year_start": min(s["year_start"] for s in shards),
            "year_end": max(s["year_end"] for s in shards),
            "record_count": count,
            "source_snapshot_sha256": source_sha256,
            "event_shards": shards,
            "raw_shards": partners,
            "lens_ids": list(LENS_IDS),
            "scope": "Load the existing provider records for this country/year; lens templates do not assert new political relationships.",
        }
        descriptor = _write(
            output, f"./data/semantic/partitions/{country}/{year}.json", partition
        )
        partitions.append(
            {
                **{
                    key: partition[key]
                    for key in (
                        "country_code",
                        "partition_year",
                        "year_start",
                        "year_end",
                        "record_count",
                    )
                },
                **descriptor,
            }
        )
    record_count = len(nodes)
    concepts = _concepts()
    datasets = manifest["datasets"]
    event_dataset = next(item for item in datasets if item["id"] == ged.DATASET_ID)
    anchors = [
        {
            "id": ged.DATASET_ID,
            "kind": "dataset",
            "label": "UCDP GED 26.1",
            "dataset_id": ged.DATASET_ID,
            **{key: event_dataset[key] for key in ("url", "license", "version")},
        },
        *concepts,
    ]
    edges = []
    for node in nodes:
        edges.extend(
            [
                {
                    "source": node["id"],
                    "target": ged.DATASET_ID,
                    "predicate": "prov:wasDerivedFrom",
                    "lens": "prov-o",
                    "source_fields": ["dataset_id", "provider_id"],
                },
                {
                    "source": node["id"],
                    "target": node["concept"]["id"],
                    "predicate": "dcterms:subject",
                    "lens": "skos",
                    "source_fields": ["attributes.type_of_violence"],
                },
            ]
        )
    counts = {
        "record_nodes": record_count,
        "nodes": record_count + len(anchors),
        "edges": len(edges),
    }
    graph = {
        "format": GRAPH_FORMAT,
        "dataset_ids": [ged.DATASET_ID],
        "context": lenses["context"],
        "source_snapshot_sha256": source_sha256,
        "selection": {
            "method": "round_robin_country_year_then_provider_id",
            "purpose": "Navigation sample, not statistically representative",
            "requested_record_nodes": RECORD_NODE_LIMIT,
            "available_records": total,
        },
        "nodes": [*nodes, *anchors],
        "edges": edges,
        "counts": counts,
        "limitations": LIMITATIONS,
    }
    graph_descriptor = {
        **_write(output, "./data/semantic/graph-view.json", graph),
        "node_count": counts["nodes"],
        "record_node_count": record_count,
        "edge_count": counts["edges"],
    }
    annual_example = _annual_example(output, manifest, lenses)
    source_snapshots = [
        {
            "dataset_id": ged.DATASET_ID,
            "repository_path": str(ged.SNAPSHOT_DIRECTORY / "manifest.json"),
            "sha256": source_sha256,
            "archive_sha256": ged.ARCHIVE_SHA256,
            "record_count": total,
            "year_start": ged.START_YEAR,
            "year_end": ged.END_YEAR,
        }
    ]
    annual_source = repository / "data/observations/world-bank/manifest.json"
    if annual_example is not None:
        source_snapshots.append(
            {
                "dataset_id": "world-bank-wdi",
                "repository_path": "data/observations/world-bank/manifest.json",
                "sha256": _digest(annual_source.read_bytes()),
                "record_count": sum(s["count"] for s in manifest["indicator_shards"]),
            }
        )
    catalog = {
        "format": FORMAT,
        "version": VERSION,
        "built_at": snapshot["built_at"],
        "source_snapshots": source_snapshots,
        "datasets": datasets,
        "ontology_alignment": lenses["alignment_status"],
        "context": lenses["context"],
        "lenses": lenses["lenses"],
        "concepts": concepts,
        "counts": {
            "event_records": total,
            "annual_values": sum(
                s["count"] for s in manifest.get("indicator_shards", [])
            ),
            "lenses": len(LENS_IDS),
            "partitions": len(partitions),
            **counts,
        },
        "graph_view": graph_descriptor,
        "partitions": partitions,
        "examples": [annual_example] if annual_example else [],
        "limitations": LIMITATIONS,
    }
    return {"format": FORMAT, **_write(output, "./data/semantic/catalog.json", catalog)}
