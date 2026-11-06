import gzip
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from syria_analysis import historical_events as ged

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/ucdp-ged-26.1-sample.json"
BUILT_AT = "2026-11-05T18:00:00Z"


class HistoricalEventsTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]
        self.aggregate = next(row for row in self.rows if row["id"] == "46208")

    def snapshot(self, path, rows=None, **kwargs):
        return ged._write_snapshot(
            self.rows if rows is None else rows, path, built_at=BUILT_AT, **kwargs
        )

    def test_normalization_retains_exact_fields_and_nonordered_estimates(self):
        original = deepcopy(self.aggregate)
        record = ged.normalize_record(original)
        self.assertEqual(original, self.aggregate)
        self.assertEqual(record["attributes"], original)
        self.assertEqual(len(record["attributes"]), 49)
        self.assertEqual(record["id"], "ucdp-ged:26.1:46208")
        self.assertEqual(record["provider_id"], "46208")
        self.assertEqual(record["country_code"], "SY")
        self.assertEqual(record["country"], original["country"])
        self.assertEqual(record["date_start"], original["date_start"][:10])
        self.assertIn("00:00:00", record["attributes"]["date_start"])
        self.assertEqual(
            [record["attributes"][name] for name in ("low", "best", "high")],
            ["5", "6", "5"],
        )
        self.assertIn("provider_estimates_not_ordered", record["quality_flags"])
        self.assertNotIn("aggregate_reporting", record["quality_flags"])
        aggregate = next(row for row in self.rows if row["event_clarity"] == "2")
        self.assertIn(
            "aggregate_reporting", ged.normalize_record(aggregate)["quality_flags"]
        )
        self.assertEqual(record["raw_record_sha256"], ged.raw_record_sha256(original))
        self.assertEqual(record["source_locator"], "GEDEvent_v26_1.csv; id=46208")

    def test_unknown_precision_reversed_dates_and_bad_coordinates_fail_closed(self):
        for field, value in [
            ("where_prec", "99"),
            ("date_prec", "0"),
            ("event_clarity", "7"),
            ("date_end", "2000-01-01 00:00:00.000"),
            ("latitude", "nan"),
            ("longitude", "181"),
            ("best", "6.0"),
        ]:
            row = {**self.aggregate, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                ged.normalize_record(row)
        with self.assertRaises(ValueError):
            ged.normalize_record(
                {k: v for k, v in self.aggregate.items() if k != "relid"}
            )

    def test_scope_filter_decodes_a_view_and_removes_whole_rows(self):
        for text in ["UAE", "D%75bai", "Abu-Dhabi", "Ｅｍｉｒａｔｉ", "D&#117;bai"]:
            self.assertTrue(ged.excluded_text(text))
        self.assertFalse(ged.excluded_text("Caucasus Emirate"))
        blocked = {**self.aggregate, "source_original": "An Emirati statement"}
        with self.assertRaises(ValueError):
            ged.normalize_record(blocked)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot"
            manifest = self.snapshot(output, rows=[self.aggregate, blocked])
            self.assertEqual(manifest["selection"]["retained_records"], 1)
            self.assertEqual(manifest["selection"]["excluded_whole_records"], 1)
            raw = ged.validate_snapshot(output)["raw_shards"][0]
            saved = json.loads(
                ged._snapshot_file(output, raw).read_text(encoding="utf-8")
            )["records"][0]
            self.assertEqual(saved["attributes"], self.aggregate)

    def test_partitions_are_deterministic_bounded_and_exactly_joinable(self):
        rows = [row for row in self.rows if row["id"] in {"46208", "46218", "46221"}]
        self.assertEqual(len(rows), 3)
        largest = max(
            len(
                ged._encoded_pair(
                    ged.normalize_record(row), "./data/events-raw/SY/2012-001.json"
                )[1]
            )
            for row in rows
        )
        limit = largest + 32
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "one", Path(directory) / "two"
            a = self.snapshot(first, rows=rows, max_shard_bytes=limit)
            b = self.snapshot(second, rows=list(reversed(rows)), max_shard_bytes=limit)
            self.assertEqual(a, b)
            self.assertGreater(len(a["event_shards"]), 1)
            self.assertEqual(len(a["event_shards"]), len(a["raw_shards"]))
            ged.validate_snapshot(first)
            for item in a["event_shards"] + a["raw_shards"]:
                self.assertLessEqual(item["bytes"], limit)
                one = ged._snapshot_file(first, item)
                two = ged._snapshot_file(second, item)
                self.assertEqual(one.read_bytes(), two.read_bytes())
            point = json.loads(
                ged._snapshot_file(first, a["event_shards"][0]).read_text(
                    encoding="utf-8"
                )
            )["records"][0]
            self.assertEqual(set(point["attributes"]), set(ged.COMPACT_COLUMNS))
            self.assertNotIn("source_article", point["attributes"])
            raw_item = next(
                item for item in a["raw_shards"] if item["path"] == point["raw_shard"]
            )
            full = json.loads(
                ged._snapshot_file(first, raw_item).read_text(encoding="utf-8")
            )["records"][0]
            self.assertEqual(point["id"], full["id"])
            self.assertEqual(
                point["raw_record_sha256"], ged.raw_record_sha256(full["attributes"])
            )

    def test_duplicate_rows_or_too_small_parts_leave_no_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "duplicate"
            with self.assertRaises(ValueError):
                self.snapshot(output, rows=[self.aggregate, self.aggregate])
            self.assertFalse(output.exists())
            output = Path(directory) / "undersized"
            with self.assertRaises(ValueError):
                self.snapshot(output, rows=[self.aggregate], max_shard_bytes=1024)
            self.assertFalse(output.exists())
            output = Path(directory) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("preserve")
            with self.assertRaises(ValueError):
                self.snapshot(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_unpinned_archive_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, output = Path(directory) / "unknown.zip", Path(directory) / "out"
            archive.write_bytes(b"not the official archive")
            with self.assertRaises(ValueError):
                ged.create_snapshot(archive, output)
            self.assertFalse(output.exists())

    def test_tampered_or_traversing_assets_cannot_be_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / ged.SNAPSHOT_DIRECTORY
            manifest = self.snapshot(snapshot)
            path = ged._snapshot_file(snapshot, manifest["raw_shards"][0])
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                ged.build_static_bundle(root, root / "dist")
            self.assertFalse((root / "dist").exists())
            item = {**manifest["event_shards"][0], "path": "./data/../../secret.json"}
            with self.assertRaises(ValueError):
                ged._snapshot_file(snapshot, item)

    def test_static_copy_is_idempotent_and_never_copies_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot, output = root / ged.SNAPSHOT_DIRECTORY, root / "dist"
            manifest = self.snapshot(snapshot)
            (snapshot / "provenance").mkdir()
            (snapshot / "provenance" / "do-not-serve.pdf").write_bytes(b"archival only")
            fragment = ged.build_static_bundle(root, output)
            self.assertEqual(fragment["format"], "policy-observation-atlas/1")
            self.assertEqual(ged.build_static_bundle(root, output), fragment)
            paths = list(output.rglob("*.*"))
            self.assertEqual(
                len(paths), len(manifest["event_shards"]) + len(manifest["raw_shards"])
            )
            self.assertFalse(any(path.suffix == ".pdf" for path in paths))
            target = output / manifest["event_shards"][0]["path"].removeprefix("./")
            target.write_text("changed")
            with self.assertRaises(ValueError):
                ged.build_static_bundle(root, output)
            self.assertEqual(target.read_text(encoding="utf-8"), "changed")

    def test_served_gzip_is_deterministic_and_preserves_every_original_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / ged.SNAPSHOT_DIRECTORY
            source_manifest = self.snapshot(snapshot)
            before = {
                path.relative_to(snapshot): path.read_bytes()
                for path in snapshot.rglob("*.json")
            }
            first, second = root / "one", root / "two"
            a = ged.build_static_bundle(root, first)
            b = ged.build_static_bundle(root, second)
            self.assertEqual(a, b)
            original = {row["id"]: row for row in self.rows}
            seen = set()
            for compact_meta, raw_meta in zip(
                a["event_shards"], a["raw_shards"], strict=True
            ):
                path = raw_meta["path"].removeprefix("./")
                encoded = (first / path).read_bytes()
                self.assertEqual(encoded, (second / path).read_bytes())
                self.assertEqual(encoded[:4], b"\x1f\x8b\x08\x00")
                self.assertEqual(encoded[4:8], b"\x00\x00\x00\x00")
                self.assertEqual(encoded[9], 255)
                self.assertEqual(raw_meta["encoding"], "gzip")
                self.assertTrue(path.endswith(".json.gz"))
                self.assertEqual(raw_meta["bytes"], len(encoded))
                self.assertEqual(
                    raw_meta["sha256"], hashlib.sha256(encoded).hexdigest()
                )
                decoded = gzip.decompress(encoded)
                self.assertEqual(raw_meta["decoded_bytes"], len(decoded))
                self.assertEqual(
                    raw_meta["decoded_sha256"], hashlib.sha256(decoded).hexdigest()
                )
                self.assertLessEqual(len(decoded), ged.MAX_SHARD_BYTES)
                compact_body = (
                    first / compact_meta["path"].removeprefix("./")
                ).read_bytes()
                self.assertEqual(
                    compact_meta["sha256"], hashlib.sha256(compact_body).hexdigest()
                )
                self.assertEqual(compact_meta["bytes"], len(compact_body))
                points = json.loads(compact_body)["records"]
                full = json.loads(decoded)["records"]
                self.assertEqual(len(points), raw_meta["count"])
                for point, record in zip(points, full, strict=True):
                    seen.add(record["provider_id"])
                    self.assertEqual(
                        record["attributes"], original[record["provider_id"]]
                    )
                    self.assertEqual(record["raw_shard"], raw_meta["path"])
                    self.assertEqual(point["raw_shard"], record["raw_shard"])
                    self.assertEqual(point["id"], record["id"])
                    self.assertEqual(
                        record["raw_record_sha256"],
                        ged.raw_record_sha256(record["attributes"]),
                    )
            self.assertEqual(seen, set(original))
            self.assertEqual(
                before,
                {
                    path.relative_to(snapshot): path.read_bytes()
                    for path in snapshot.rglob("*.json")
                },
            )
            self.assertEqual(ged.validate_snapshot(snapshot), source_manifest)
            self.assertFalse(list((first / "data/events-raw").rglob("*.json")))

    def test_longer_served_references_repartition_without_exceeding_decoded_bound(self):
        rows = [row for row in self.rows if row["id"] in {"46208", "46218", "46221"}]
        old_path = "./data/events-raw/SY/2012-001.json"
        original_bodies = [
            ged._encoded_pair(ged.normalize_record(row), old_path)[1] for row in rows
        ]
        limit = len(ged._PART_PREFIX + b",".join(original_bodies) + ged._PART_SUFFIX)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / ged.SNAPSHOT_DIRECTORY
            manifest = self.snapshot(snapshot, rows=rows, max_shard_bytes=limit)
            self.assertEqual(len(manifest["raw_shards"]), 1)
            with patch.object(ged, "MAX_SHARD_BYTES", limit):
                served = ged.build_static_bundle(root, root / "dist")
            self.assertGreater(len(served["raw_shards"]), 1)
            self.assertEqual(sum(row["count"] for row in served["raw_shards"]), 3)
            self.assertTrue(
                all(row["decoded_bytes"] <= limit for row in served["raw_shards"])
            )
            self.assertTrue(
                all(row["bytes"] <= limit for row in served["event_shards"])
            )
            self.assertEqual(ged.validate_snapshot(snapshot), manifest)

    def test_changed_gzip_asset_is_refused_and_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.snapshot(root / ged.SNAPSHOT_DIRECTORY)
            output = root / "dist"
            manifest = ged.build_static_bundle(root, output)
            raw = output / manifest["raw_shards"][0]["path"].removeprefix("./")
            encoded = raw.read_bytes()
            changed = encoded[:-1] + bytes([encoded[-1] ^ 1])
            raw.write_bytes(changed)
            with self.assertRaises(ValueError):
                ged.build_static_bundle(root, output)
            self.assertEqual(raw.read_bytes(), changed)

    def test_legacy_uncompressed_evidence_requires_fresh_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.snapshot(root / ged.SNAPSHOT_DIRECTORY)
            output = root / "dist"
            legacy = output / source["raw_shards"][0]["path"].removeprefix("./")
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"previous evidence asset")
            with self.assertRaisesRegex(ValueError, "fresh static output"):
                ged.build_static_bundle(root, output)
            self.assertEqual(legacy.read_bytes(), b"previous evidence asset")

    def test_official_receipts_and_codebook_hash_are_preserved(self):
        provenance = ROOT / ged.SNAPSHOT_DIRECTORY / "provenance"
        codebook = provenance / "ged261.pdf"
        self.assertEqual(
            hashlib.sha256(codebook.read_bytes()).hexdigest(), ged.CODEBOOK_SHA256
        )
        receipts = json.loads(
            (provenance / "download-receipts.json").read_text(encoding="utf-8")
        )["assets"]
        archive = next(row for row in receipts if row["url"] == ged.ARCHIVE_URL)
        self.assertEqual(archive["http_status"], 200)
        self.assertFalse(archive["credentials_used"])
        self.assertEqual(archive["sha256"], ged.ARCHIVE_SHA256)
        self.assertEqual(archive["bytes"], ged.ARCHIVE_BYTES)
        self.assertIn(
            "https://creativecommons.org/licenses/by/4.0/",
            (provenance / "ucdp-downloads-index.html").read_text(encoding="utf-8"),
        )

    def test_committed_real_snapshot_integrity_and_coverage(self):
        manifest = ged.validate_snapshot(ROOT / ged.SNAPSHOT_DIRECTORY)
        self.assertEqual(manifest["selection"]["source_rows"], 417968)
        self.assertEqual(manifest["selection"]["scope_candidates"], 120936)
        self.assertEqual(manifest["selection"]["retained_records"], 120576)
        self.assertEqual(manifest["selection"]["excluded_whole_records"], 360)
        self.assertEqual(manifest["selection"]["provider_year_start"], 2000)
        self.assertEqual(manifest["selection"]["provider_year_end"], 2025)
        self.assertEqual(len(manifest["event_shards"]), 297)
        self.assertEqual(len(manifest["raw_shards"]), 297)
        self.assertEqual(
            {row["code"]: row["event_count"] for row in manifest["countries"]},
            {
                "SY": 88284,
                "IQ": 9030,
                "LB": 1791,
                "IL": 11187,
                "JO": 8,
                "EG": 824,
                "YE": 6103,
                "IR": 687,
                "TR": 2662,
            },
        )
        self.assertEqual(
            manifest["quality_flag_counts"]["provider_estimates_not_ordered"], 683
        )
        self.assertEqual(manifest["quality_flag_counts"]["aggregate_reporting"], 2099)
        self.assertLessEqual(
            max(
                row["bytes"]
                for row in manifest["event_shards"] + manifest["raw_shards"]
            ),
            ged.MAX_SHARD_BYTES,
        )
        recent = [
            row
            for row in manifest["event_shards"]
            if row["country_code"] == "SY" and row["year_end"] >= 2020
        ]
        self.assertEqual(sum(row["count"] for row in recent), 5263)
        self.assertLess(sum(row["bytes"] for row in recent), 5 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
