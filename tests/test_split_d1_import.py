"""Exact SQL source preservation, bounded parts and transactional resume markers."""

import base64
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "split_d1_import", ROOT / "scripts/split_d1_import.py"
)
splitter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(splitter)


def execute_part(connection, body):
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;\n" + body.decode("utf-8") + "\nCOMMIT;"
        )
    except sqlite3.Error:
        connection.rollback()
        raise


def table_rows(connection):
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name!='research_import_parts' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1,2').fetchall()
        for table in tables
    }


class SplitD1ImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "research.sql"
        statements = [
            "-- Quoted semicolons and multiple statements per physical line are intentional.\r\nPRAGMA foreign_keys=ON;",
            "CREATE TABLE research_meta (\n key TEXT PRIMARY KEY,\n value TEXT CHECK(json_valid(value))\n);",
            "CREATE TABLE events (id INTEGER PRIMARY KEY, actor TEXT, source TEXT, value REAL, missing TEXT); CREATE TABLE log (id INTEGER, note TEXT);",
            "CREATE TABLE manifests (id TEXT PRIMARY KEY, text TEXT CHECK(json_valid(text)));",
            "CREATE TRIGGER preserve_notes AFTER INSERT ON events BEGIN\n INSERT INTO log VALUES (new.id, 'trigger; O''Brien — دمشق');\nEND;",
        ]
        for number in range(160):
            text = "L'été; O'Brien — دمشق\nsecond line; 日本\r\n" + str(number)
            literal = "'" + text.replace("'", "''") + "'"
            statements.append(
                f"INSERT INTO events VALUES({number},'A; B',{literal},{number}.125,NULL);"
            )
        pretty = json.dumps(
            {
                "name": "actual test fixture; not evidence",
                "unicode": "界; دمشق",
                "lines": ["one", "two"],
            },
            ensure_ascii=False,
            indent=2,
        )
        statements.extend(
            [
                "INSERT INTO manifests VALUES('source', '"
                + pretty.replace("'", "''")
                + "');",
                "CREATE INDEX event_actors ON events(actor);",
                "INSERT INTO research_meta VALUES('counts','{\"events\":160}');",
                "INSERT INTO research_meta VALUES('state','\"ready\"');",
            ]
        )
        self.original = (
            "\n".join(statements) + "\r\n-- untouched trailing comment;\r\n"
        ).encode("utf-8")
        self.source.write_bytes(self.original)
        self.output = self.root / "parts"

    def split(self, **kwargs):
        return splitter.split_import(self.source, self.output, max_bytes=4096, **kwargs)

    def test_complete_chunk_replay_matches_every_original_row_and_manifest_field(self):
        manifest = self.split()
        self.assertGreater(manifest["part_count"], 3)
        baseline, replay = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
        self.addCleanup(baseline.close)
        self.addCleanup(replay.close)
        baseline.executescript(self.original.decode("utf-8"))
        replay.execute("PRAGMA foreign_keys=ON")
        recovered = []
        for item in manifest["parts"]:
            body = (self.output / item["path"]).read_bytes()
            self.assertLessEqual(len(body), 4096)
            self.assertEqual(len(body), item["bytes"])
            self.assertEqual(hashlib.sha256(body).hexdigest(), item["sha256"])
            self.assertEqual(
                hashlib.md5(body, usedforsecurity=False).hexdigest(), item["md5"]
            )
            self.assertEqual(
                base64.b64decode(item["md5_base64"]),
                hashlib.md5(body, usedforsecurity=False).digest(),
            )
            payload = b"".join(
                body[s["file_start"] : s["file_start"] + s["bytes"]]
                for s in item["source_payload"]["file_segments"]
            )
            original = self.original[
                item["source_payload"]["start"] : item["source_payload"]["end"]
            ]
            self.assertEqual(payload, original)
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(), item["source_payload"]["sha256"]
            )
            recovered.append(payload)
            execute_part(replay, body)
            checkpoints = replay.execute(
                "SELECT part_number,source_sql_sha256,source_payload_sha256,source_start,source_bytes,source_statements,prior_parts FROM research_import_parts ORDER BY part_number"
            ).fetchall()
            self.assertEqual(len(checkpoints), item["sequence"])
            self.assertEqual(
                checkpoints[-1],
                (
                    item["sequence"],
                    manifest["source_sql"]["sha256"],
                    item["source_payload"]["sha256"],
                    item["source_payload"]["start"],
                    item["source_payload"]["bytes"],
                    item["source_payload"]["statements"],
                    item["sequence"] - 1,
                ),
            )
            ready = replay.execute(
                "SELECT value FROM research_meta WHERE key='state'"
            ).fetchone()
            self.assertEqual(ready, ('"ready"',) if item["publishes_ready"] else None)
        self.assertEqual(b"".join(recovered), self.original)
        self.assertEqual(table_rows(replay), table_rows(baseline))
        self.assertEqual(replay.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        self.assertEqual(replay.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(
            sum(p["source_payload"]["statements"] for p in manifest["parts"]),
            manifest["source_sql"]["statements"],
        )
        self.assertTrue(manifest["parts"][-1]["publishes_ready"])
        self.assertFalse(any(p["publishes_ready"] for p in manifest["parts"][:-1]))
        units = list(splitter.sql_units(self.output / manifest["parts"][-1]["path"]))
        last = [body for body, statement in units if statement][-1]
        self.assertTrue(splitter._READY.fullmatch(last.decode("utf-8")))

    def test_source_units_preserve_multiline_comments_trigger_and_unicode_bytes(self):
        units = list(splitter.sql_units(self.source))
        self.assertEqual(b"".join(body for body, _ in units), self.original)
        self.assertTrue(
            any(b"CREATE TRIGGER" in body and b"END;" in body for body, _ in units)
        )
        self.assertTrue(
            any(b"\r\n" in body and "日本" in body.decode("utf-8") for body, _ in units)
        )
        self.assertEqual(sum(b"CREATE TABLE" in body for body, _ in units), 4)
        self.assertFalse(units[-1][1])

    def test_out_of_order_or_duplicate_import_rolls_back_without_new_checkpoint(self):
        manifest = self.split()
        database = sqlite3.connect(":memory:")
        self.addCleanup(database.close)
        database.execute("PRAGMA foreign_keys=ON")
        execute_part(
            database, (self.output / manifest["parts"][0]["path"]).read_bytes()
        )
        before = table_rows(database)
        with self.assertRaises(sqlite3.IntegrityError):
            execute_part(
                database, (self.output / manifest["parts"][2]["path"]).read_bytes()
            )
        self.assertEqual(table_rows(database), before)
        self.assertEqual(
            database.execute("SELECT COUNT(*) FROM research_import_parts").fetchone()[
                0
            ],
            1,
        )
        execute_part(
            database, (self.output / manifest["parts"][1]["path"]).read_bytes()
        )
        before = table_rows(database)
        with self.assertRaises(sqlite3.IntegrityError):
            execute_part(
                database, (self.output / manifest["parts"][1]["path"]).read_bytes()
            )
        self.assertEqual(table_rows(database), before)
        self.assertEqual(
            database.execute("SELECT COUNT(*) FROM research_import_parts").fetchone()[
                0
            ],
            2,
        )

    def test_deterministic_parts_and_existing_output_refusal(self):
        a = self.split()
        other = self.root / "other"
        b = splitter.split_import(self.source, other, max_bytes=4096)
        self.assertEqual(a, b)
        for item in a["parts"]:
            self.assertEqual(
                (self.output / item["path"]).read_bytes(),
                (other / item["path"]).read_bytes(),
            )
        marker = self.output / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fresh output"):
            self.split()
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_wrong_hash_missing_or_early_ready_incomplete_sql_and_transactions_fail(
        self,
    ):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.split(expected_sha256="0" * 64)
        self.assertFalse(self.output.exists())
        cases = [
            (b"CREATE TABLE only_one(id INTEGER);", "ready marker"),
            (
                self.original + b"INSERT INTO events VALUES(900,'a','b',0,NULL);",
                "final SQL",
            ),
            (self.original + b"INSERT INTO events", "incomplete"),
            (b"BEGIN;\n" + self.original, "transaction wrappers"),
        ]
        for source, message in cases:
            self.source.write_bytes(source)
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.split()
            self.assertFalse(self.output.exists())

    def test_statement_and_part_bounds_count_utf8_bytes(self):
        self.source.write_text(
            "INSERT INTO anything VALUES('" + "界" * 40_000 + "');", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "95,000-byte"):
            self.split()
        self.assertFalse(self.output.exists())
        self.source.write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, "between"):
            splitter.split_import(
                self.source, self.output, max_bytes=splitter.MAX_PART_BYTES + 1
            )
        with self.assertRaisesRegex(ValueError, "part bound"):
            splitter.split_import(self.source, self.output, max_bytes=1024)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
