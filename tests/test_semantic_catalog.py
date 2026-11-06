"""Source fidelity, scoped vocabulary mappings and bounded lazy graph contracts."""

import hashlib
import json
import shutil
import tempfile
import unittest
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from syria_analysis import (
    country_context,
)
from syria_analysis import (
    historical_events as ged,
)
from syria_analysis import (
    semantic_catalog as sem,
)
from syria_analysis.observations import _load_shard

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/semantic_catalog.schema.json").read_bytes())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def read_asset(output, descriptor):
    body = (output / descriptor["path"]).read_bytes()
    if (
        len(body) != descriptor["bytes"]
        or hashlib.sha256(body).hexdigest() != descriptor["sha256"]
    ):
        raise AssertionError("Published descriptor does not identify its asset")
    return json.loads(body)


class SemanticCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "ontology").mkdir()
        shutil.copyfile(
            ROOT / "ontology/semantic-lenses.json",
            self.root / "ontology/semantic-lenses.json",
        )
        rows = json.loads(
            (ROOT / "tests/fixtures/ucdp-ged-26.1-sample.json").read_bytes()
        )["records"]
        ged._write_snapshot(
            rows, self.root / ged.SNAPSHOT_DIRECTORY, built_at="2026-11-06T00:00:00Z"
        )
        self.output = self.root / "atlas"
        self.manifest = ged.build_static_bundle(self.root, self.output)
        self.fixture = json.loads(
            (ROOT / "tests/fixtures/wdi-sosa-example.json").read_bytes()
        )
        row = self.fixture["record"]
        path = self.output / "data/indicators/SY-01.json"
        path.parent.mkdir()
        body = ged._json_bytes({"records": [row]})
        path.write_bytes(body)
        self.manifest["indicator_shards"] = [
            {
                "path": "./data/indicators/SY-01.json",
                "dataset_id": "world-bank-wdi",
                "country_code": "SY",
                "count": 1,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        ]
        self.manifest["datasets"].append(
            {
                "id": "world-bank-wdi",
                "kind": "country_indicator",
                "title": "World Development Indicators",
                "version": "2026-10-08",
                "publisher": "World Bank and source providers",
                "url": "https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators",
                "license": "CC-BY-4.0; World Bank dataset terms also apply",
                "sha256": self.fixture["provenance"]["source_snapshot_manifest_sha256"],
            }
        )
        source = self.root / "data/observations/world-bank/manifest.json"
        source.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "data/observations/world-bank/manifest.json", source)

    def build(self):
        descriptor = sem.build_semantic_catalog(self.root, self.output, self.manifest)
        catalog = read_asset(self.output, descriptor)
        graph = read_asset(self.output, catalog["graph_view"])
        return descriptor, catalog, graph

    def test_lenses_catalog_graph_and_partitions_follow_versioned_schema(self):
        Draft202012Validator.check_schema(SCHEMA)
        _, catalog, graph = self.build()
        for data in [sem.load_lenses(self.root), catalog, graph]:
            VALIDATOR.validate(data)
        for descriptor in catalog["partitions"]:
            VALIDATOR.validate(read_asset(self.output, descriptor))
        self.assertEqual(catalog["counts"]["event_records"], 9)
        self.assertEqual(catalog["counts"]["annual_values"], 1)
        self.assertEqual(catalog["counts"]["record_nodes"], 9)
        self.assertEqual([lens["id"] for lens in catalog["lenses"]], list(sem.LENS_IDS))

    def test_graph_only_connects_actual_record_lineage_and_provider_categories(self):
        _, catalog, graph = self.build()
        nodes = {node["id"]: node for node in graph["nodes"]}
        records = [node for node in nodes.values() if node["kind"] == "conflict_event"]
        self.assertEqual(len(records), 9)
        self.assertEqual(len(graph["edges"]), 18)
        self.assertEqual(
            {edge["predicate"] for edge in graph["edges"]},
            {"prov:wasDerivedFrom", "dcterms:subject"},
        )
        index = {item["path"]: item for item in self.manifest["event_shards"]}
        for node in records:
            row = next(
                r
                for r in _load_shard(self.output, index[node["compact_shard"]])
                if r["id"] == node["id"]
            )
            for field in [
                "label",
                "date_start",
                "date_end",
                "latitude",
                "longitude",
                "raw_record_sha256",
                "raw_shard",
            ]:
                self.assertEqual(node[field], row[field])
            self.assertEqual(
                node["concept"]["value"], row["attributes"]["type_of_violence"]
            )
            self.assertEqual(
                node["precision"]["where_prec"], row["attributes"]["where_prec"]
            )
        for edge in graph["edges"]:
            self.assertIn(edge["source"], nodes)
            self.assertIn(edge["target"], nodes)
            expected = (
                ged.DATASET_ID
                if edge["lens"] == "prov-o"
                else nodes[edge["source"]]["concept"]["id"]
            )
            self.assertEqual(edge["target"], expected)
        self.assertIn("not statistically representative", graph["selection"]["purpose"])
        self.assertEqual(
            graph["source_snapshot_sha256"], catalog["source_snapshots"][0]["sha256"]
        )

    def test_sosa_example_uses_actual_annual_value_and_retains_raw_unit(self):
        _, catalog, _ = self.build()
        example = catalog["examples"][0]
        actual = self.fixture["record"]
        self.assertEqual(example["id"], "wdi:2:SYR:SP.POP.TOTL:2024")
        self.assertEqual(example["value"], 24672760)
        self.assertEqual(example["unit"], "persons")
        self.assertEqual(example["evidence_fields"]["attributes.unit"], "")
        self.assertEqual(
            example["attributes_sha256"], ged.raw_record_sha256(actual["attributes"])
        )
        self.assertEqual(catalog["lenses"][-1]["applies_to"], ["country_indicator"])
        self.assertIn("estimate", example["qualification"])
        self.assertEqual(_load_shard(self.output, example["shard"]), [actual])

    def test_partitions_reuse_registered_shards_without_duplicating_records(self):
        _, catalog, _ = self.build()
        self.assertEqual(sum(item["record_count"] for item in catalog["partitions"]), 9)
        expected = {item["path"] for item in self.manifest["event_shards"]}
        actual = set()
        for item in catalog["partitions"]:
            partition = read_asset(self.output, item)
            self.assertNotIn("records", partition)
            self.assertNotIn("nodes", partition)
            self.assertEqual(
                sum(s["count"] for s in partition["event_shards"]), item["record_count"]
            )
            actual.update(s["path"] for s in partition["event_shards"])
        self.assertEqual(actual, expected)

    def test_deterministic_repeat_build_and_changed_asset_refusal(self):
        descriptor, _, _ = self.build()
        self.assertEqual(
            sem.build_semantic_catalog(self.root, self.output, self.manifest),
            descriptor,
        )
        path = self.output / descriptor["path"]
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed semantic asset"):
            self.build()
        self.assertEqual(path.read_bytes(), b"changed")

    def test_tampered_shard_missing_partner_or_wrong_total_is_refused(self):
        original = deepcopy(self.manifest)
        self.manifest["event_shards"][0]["count"] += 1
        with self.assertRaisesRegex(ValueError, "immutable source count"):
            self.build()
        self.manifest = deepcopy(original)
        self.manifest["raw_shards"] = []
        with self.assertRaisesRegex(ValueError, "evidence partner"):
            self.build()
        self.manifest = deepcopy(original)
        path = self.output / self.manifest["event_shards"][0]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "checksum or size"):
            self.build()

    def test_unknown_vocabulary_term_sensor_mapping_or_inferred_edge_is_rejected(self):
        document = sem.load_lenses(self.root)
        document["lenses"][0]["terms"][0]["url"] = "https://example.org/not-prov"
        path = self.root / "ontology/semantic-lenses.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "namespace"):
            sem.load_lenses(self.root)
        document = json.loads((ROOT / "ontology/semantic-lenses.json").read_bytes())
        document["lenses"][-1]["applies_to"] = ["conflict_event"]
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "annual source"):
            sem.load_lenses(self.root)
        document = json.loads((ROOT / "ontology/semantic-lenses.json").read_bytes())
        path.write_text(json.dumps(document), encoding="utf-8")
        _, _, graph = self.build()
        graph["edges"][0]["predicate"] = "politically:controls"
        self.assertTrue(list(VALIDATOR.iter_errors(graph)))

    def test_external_traversal_and_symlink_navigation_targets_are_refused(self):
        for name in [
            "https://example.org/data.json",
            "./data/../secret.json",
            "./data/../../secret.json",
            "/data/file.json",
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                sem._path(self.output, name)
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.output / "data/semantic").symlink_to(
                outside, target_is_directory=True
            )
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform")
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.build()


class RealSemanticCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name)
        events = ged.build_static_bundle(ROOT, cls.output)
        annual = country_context.build_static_bundle(ROOT, cls.output)
        cls.manifest = {
            **events,
            "datasets": events["datasets"] + annual["datasets"],
            "indicator_shards": annual["indicator_shards"],
        }
        cls.descriptor = sem.build_semantic_catalog(ROOT, cls.output, cls.manifest)
        cls.catalog = read_asset(cls.output, cls.descriptor)
        cls.graph = read_asset(cls.output, cls.catalog["graph_view"])

    def test_actual_catalog_has_2048_distinct_records_and_all_188_lazy_partitions(self):
        VALIDATOR.validate(self.catalog)
        VALIDATOR.validate(self.graph)
        self.assertEqual(self.catalog["counts"]["event_records"], 120576)
        self.assertEqual(self.catalog["counts"]["annual_values"], 15272)
        self.assertEqual(self.catalog["counts"]["record_nodes"], 2048)
        self.assertEqual(self.catalog["counts"]["partitions"], 188)
        self.assertEqual(len({n["id"] for n in self.graph["nodes"]}), 2052)
        self.assertEqual(
            sum(p["record_count"] for p in self.catalog["partitions"]), 120576
        )
        self.assertLess(self.catalog["graph_view"]["bytes"], sem.MAX_ASSET_BYTES)
        self.assertLess(
            sum(p.stat().st_size for p in self.output.rglob("*") if p.is_file()),
            180 * 1024 * 1024,
        )
        for partition in self.catalog["partitions"]:
            VALIDATOR.validate(read_asset(self.output, partition))

    def test_all_2048_index_nodes_reopen_exact_real_full_records(self):
        grouped = defaultdict(list)
        for node in self.graph["nodes"]:
            if node["kind"] == "conflict_event":
                grouped[node["raw_shard"]].append(node)
        raw_index = {s["path"]: s for s in self.manifest["raw_shards"]}
        checked = 0
        for path, nodes in grouped.items():
            records = {r["id"]: r for r in _load_shard(self.output, raw_index[path])}
            for node in nodes:
                record = records[node["id"]]
                self.assertEqual(len(record["attributes"]), 49)
                self.assertEqual(
                    ged.raw_record_sha256(record["attributes"]),
                    node["raw_record_sha256"],
                )
                self.assertEqual(record["latitude"], node["latitude"])
                self.assertEqual(record["longitude"], node["longitude"])
                self.assertEqual(
                    record["attributes"]["type_of_violence"], node["concept"]["value"]
                )
                self.assertFalse(
                    any(ged.excluded_text(v) for v in record["attributes"].values())
                )
                checked += 1
        self.assertEqual(checked, 2048)


if __name__ == "__main__":
    unittest.main()
