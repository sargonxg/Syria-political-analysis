import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from syria_analysis import historical_events as ged

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "research_database_builder", ROOT / "scripts/build_research_database.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ResearchDatabaseTests(unittest.TestCase):
    def fixture(self, repository, *, large=False):
        rows = json.loads(
            (ROOT / "tests/fixtures/ucdp-ged-26.1-sample.json").read_text(
                encoding="utf-8"
            )
        )["records"][:2]
        rows[0]["source_article"] = "x" * 100_000 if large else "L'été — دمشق; O'Brien"
        ged._write_snapshot(
            rows, repository / ged.SNAPSHOT_DIRECTORY, built_at="2026-11-05T18:00:00Z"
        )
        source = {
            "id": "fixture-source",
            "name": "Fixture source",
            "type": "test",
            "url": "https://example.org/",
            "description": "界" * 11_000,
            "evidence": [
                {"basis": "Synthetic test fixture", "url": "https://example.org/about"}
            ],
        }
        path = repository / "data/sources/registry.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([source], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return rows, path.read_bytes()

    def test_full_field_roundtrip_utf8_manifests_and_deterministic_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "source"
            rows, source_bytes = self.fixture(repository)
            a = builder.build_database(
                repository, Path(directory) / "first", include_country_context=False
            )
            b = builder.build_database(
                repository, Path(directory) / "second", include_country_context=False
            )
            self.assertEqual(a["sql_sha256"], b["sql_sha256"])
            self.assertEqual(a["snapshot_id"], b["snapshot_id"])
            self.assertLess(a["maximum_statement_bytes"], 100_000)
            sql = (Path(directory) / "first/research.sql").read_text(encoding="utf-8")
            self.assertNotIn("BEGIN TRANSACTION", sql)
            self.assertNotIn("DROP TABLE", sql)
            connection = sqlite3.connect(":memory:")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(sql)
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(), []
            )
            saved = {
                json.loads(row[0])["provider_id"]: json.loads(row[0])["attributes"]
                for row in connection.execute("SELECT record_json FROM events")
            }
            self.assertEqual(saved, {row["id"]: row for row in rows})
            restored = "".join(
                row[0]
                for row in connection.execute(
                    "SELECT text FROM manifest_chunks WHERE manifest_id='source-catalogue' ORDER BY part"
                )
            )
            self.assertEqual(restored.encode("utf-8"), source_bytes)
            self.assertEqual(
                connection.execute("SELECT count(*) FROM events").fetchone()[0],
                a["counts"]["events"],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT value FROM research_meta WHERE key='state'"
                ).fetchone()[0],
                '"ready"',
            )
            self.assertEqual(hashlib.md5(sql.encode()).hexdigest(), a["sql_md5"])
            connection.close()

    def test_existing_output_is_refused_and_source_snapshot_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, output = Path(directory) / "source", Path(directory) / "out"
            self.fixture(repository)
            manifest = repository / ged.SNAPSHOT_DIRECTORY / "manifest.json"
            before = manifest.read_bytes()
            builder.build_database(repository, output, include_country_context=False)
            with self.assertRaisesRegex(ValueError, "fresh output"):
                builder.build_database(
                    repository, output, include_country_context=False
                )
            self.assertEqual(manifest.read_bytes(), before)

    def test_corrupt_source_and_oversized_statement_fail_without_publishing_ready_output(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            repository, output = Path(directory) / "source", Path(directory) / "out"
            self.fixture(repository, large=True)
            with self.assertRaisesRegex(ValueError, "statement exceeds"):
                builder.build_database(
                    repository, output, include_country_context=False
                )
            self.assertFalse(output.exists())
            manifest = json.loads(
                (repository / ged.SNAPSHOT_DIRECTORY / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            raw = ged._snapshot_file(
                repository / ged.SNAPSHOT_DIRECTORY, manifest["raw_shards"][0]
            )
            raw.write_bytes(raw.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                builder.build_database(
                    repository, output, include_country_context=False
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
