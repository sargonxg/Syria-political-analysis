"""Practical query behavior and compact-to-original provenance boundaries."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from syria_analysis.historical_events import raw_record_sha256
from syria_analysis.observations import query_observations


class ObservationQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        self.full = []
        for i, year, category, precision in [(1, 2020, "1", "1"), (2, 2021, "2", "3")]:
            attrs = {
                "id": str(i),
                "side_a": "Synthetic A",
                "side_b": "Synthetic B",
                "type_of_violence": category,
                "where_prec": precision,
                "source_article": "Synthetic fixture citation, not real reporting",
                "low": "5",
                "best": "3",
                "high": "8",
            }
            self.full.append(
                {
                    "id": f"test-event:{i}",
                    "kind": "conflict_event",
                    "dataset_id": "test-events",
                    "label": "Synthetic event",
                    "country_code": "SY",
                    "date_start": f"{year}-01-02",
                    "date_end": f"{year}-01-03",
                    "source_locator": f"Synthetic fixture row {i}",
                    "attributes": attrs,
                    "raw_record_sha256": raw_record_sha256(attrs),
                    "raw_shard": "./data/raw.json",
                }
            )
        self.compact = [
            dict(
                r,
                attributes={
                    k: v for k, v in r["attributes"].items() if k != "source_article"
                },
            )
            for r in self.full
        ]
        compact_meta = self.write_shard("./data/compact.json", self.compact)
        raw_meta = self.write_shard("./data/raw.json", self.full)
        self.manifest = {
            "format": "policy-observation-atlas/1",
            "countries": [{"code": "SY", "name": "Synthetic Syria fixture"}],
            "datasets": [
                {
                    "id": "test-events",
                    "title": "Synthetic test data",
                    "version": "test",
                    "publisher": "Tests",
                    "url": "https://example.org/fixture",
                    "license": "CC0 test fixture",
                    "sha256": "a" * 64,
                }
            ],
            "event_shards": [compact_meta],
            "raw_shards": [raw_meta],
            "indicator_shards": [],
            "limitations": ["Synthetic fixture; not evidence of an actual event."],
        }
        self.save_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_shard(self, name, rows):
        raw = json.dumps({"records": rows}, ensure_ascii=False).encode()
        (self.root / name).write_bytes(raw)
        return {
            "path": name,
            "count": len(rows),
            "country_code": "SY",
            "dataset_id": "test-events",
            "year_start": 2020,
            "year_end": 2021,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def save_manifest(self):
        (self.root / "data/manifest.json").write_text(json.dumps(self.manifest))

    def test_actual_filters_and_full_original_fields_are_exported(self):
        result = query_observations(
            self.root,
            from_year=2020,
            to_year=2021,
            actor="synthetic b",
            violence_type=1,
            geography_precision=1,
        )
        self.assertEqual(result["counts"]["matched"], 1)
        attrs = result["records"][0]["attributes"]
        self.assertIn(
            "source_article", attrs, "A compact point must hydrate its original fields"
        )
        self.assertEqual(
            [attrs[k] for k in ("low", "best", "high")],
            ["5", "3", "8"],
            "Provider estimates must not be repaired or reordered",
        )

    def test_explicit_prefix_preserves_matching_count(self):
        result = query_observations(self.root, limit=1)
        self.assertEqual(
            result["counts"],
            {"matched": 2, "exported": 1, "limit": 1, "truncated": True},
        )

    def test_empty_result_stays_empty(self):
        result = query_observations(self.root, actor="No matching fixture actor")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["counts"]["matched"], 0)

    def test_event_filters_are_not_misrepresented_on_country_values(self):
        with self.assertRaisesRegex(ValueError, "do not apply"):
            query_observations(self.root, indicator="SP.POP.TOTL", actor="Synthetic A")

    def test_changed_shard_is_refused_before_use(self):
        (self.root / "data/compact.json").write_text('{"records":[]}')
        with self.assertRaisesRegex(ValueError, "checksum"):
            query_observations(self.root)

    def test_raw_row_digest_is_recomputed(self):
        self.full[0]["attributes"]["source_article"] = "Changed exact source fields"
        self.manifest["raw_shards"] = [self.write_shard("./data/raw.json", self.full)]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "canonical record digest"):
            query_observations(self.root)

    def test_raw_partner_cannot_be_substituted(self):
        self.full[0]["raw_record_sha256"] = "b" * 64
        self.manifest["raw_shards"] = [self.write_shard("./data/raw.json", self.full)]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "identity does not match"):
            query_observations(self.root)

    def test_external_or_escaping_shard_path_is_refused(self):
        for name in ["https://example.org/fixture", "../outside.json"]:
            self.manifest["event_shards"][0]["path"] = name
            self.save_manifest()
            with self.assertRaises(ValueError):
                query_observations(self.root)


if __name__ == "__main__":
    unittest.main()
