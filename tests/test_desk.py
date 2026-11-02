import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from syria_analysis.core import read_json
from syria_analysis.desk.app import Settings, create_app
from syria_analysis.desk.manage import import_public
from syria_analysis.desk.models import RecordWrite
from syria_analysis.desk.store import Conflict, Store
from syria_analysis.desk.transfer import restore_case

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "test-only-not-a-deployment-key-00000000"


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "desk.sqlite3"
        self.store = Store(self.path)
        self.case = self.store.create_case("Test research question")["id"]

    def tearDown(self):
        self.temp.cleanup()

    def source_document(self):
        source = self.store.write(
            self.case,
            RecordWrite(
                kind="source",
                title="Test institutional source",
                url="https://example.org/",
            ),
        )
        document = self.store.write(
            self.case,
            RecordWrite(
                kind="document",
                title="Test document",
                source_id=source["id"],
                body="The report records a proposal. It does not confirm implementation.",
                published_on="2020-01-01",
                reviewed_on="2026-11-02",
            ),
        )
        return source, document

    def test_claim_requires_exact_excerpt_and_locator(self):
        _, doc = self.source_document()
        data = {
            "kind": "claim",
            "title": "A proposal was recorded",
            "document_id": doc["id"],
            "excerpt": "The report records a proposal.",
            "locator": "Paragraph 1",
        }
        row = self.store.write(self.case, RecordWrite(**data))
        self.assertEqual(row["citation_provenance"]["document_revision"], 1)
        self.store.write(
            self.case,
            RecordWrite(
                kind="document",
                title=doc["title"],
                source_id=doc["source_id"],
                body=doc["body"] + " Extra context.",
            ),
            doc["id"],
            1,
        )
        self.assertEqual(
            self.store.get(row["id"])["citation_provenance"]["document_revision"], 1
        )
        self.assertEqual(self.store.get(doc["id"])["backlinks"][0]["id"], row["id"])
        with self.assertRaises(ValueError):
            self.store.write(
                self.case, RecordWrite(**(data | {"excerpt": "Invented evidence"}))
            )
        with self.assertRaises(ValidationError):
            RecordWrite(kind="claim", title="No citation")
        with self.assertRaises(ValidationError):
            RecordWrite(**(data | {"confidence": "high"}))

    def test_edits_are_versioned_and_cited_passages_cannot_be_removed(self):
        _, doc = self.source_document()
        self.store.write(
            self.case,
            RecordWrite(
                kind="claim",
                title="Proposal",
                document_id=doc["id"],
                excerpt="a proposal",
                locator="Sentence 1",
            ),
        )
        with self.assertRaises(Conflict):
            self.store.write(
                self.case,
                RecordWrite(
                    kind="document",
                    title=doc["title"],
                    source_id=doc["source_id"],
                    body="Different content",
                ),
                doc["id"],
                1,
            )
        row = self.store.write(
            self.case, RecordWrite(kind="note", title="Draft", body="Version one")
        )
        for revision in range(1, 4):
            row = self.store.write(
                self.case,
                RecordWrite(kind="note", title="Draft", body=f"Version {revision + 1}"),
                row["id"],
                revision,
            )
        with self.assertRaises(Conflict):
            self.store.write(
                self.case,
                RecordWrite(kind="note", title="Stale", body="Do not overwrite"),
                row["id"],
                1,
            )
        self.assertEqual(len(self.store.history(row["id"])), 4)
        self.assertEqual(self.store.get(row["id"])["body"], "Version 4")

    def test_case_isolation_persistence_search_and_exports(self):
        _, doc = self.source_document()
        other = self.store.create_case("Another case")["id"]
        with self.assertRaises(ValueError):
            self.store.write(
                other,
                RecordWrite(kind="note", title="Cross-case link", links=[doc["id"]]),
            )
        self.store.write(
            self.case,
            RecordWrite(
                kind="note",
                title="Housing",
                body="Arabic العربية and 100% literal",
                tags=["recovery"],
                links=[doc["id"]],
            ),
        )
        reopened = Store(self.path)
        self.assertEqual(reopened.records(self.case, "العربية")["total"], 1)
        self.assertEqual(reopened.records(self.case, "%")["total"], 1)
        self.assertEqual(reopened.records(self.case, "' OR 1=1 --")["total"], 0)
        bundle = reopened.export(self.case)
        ids = {r["id"] for r in bundle["records"]}
        self.assertTrue(
            all(
                e["source"] in ids and e["target"] in ids
                for e in bundle["relationships"]
            )
        )
        self.assertNotIn("sessions", bundle)
        self.assertEqual(len(bundle["revisions"]), 3)

    def test_backup_and_forward_schema_boundary(self):
        self.source_document()
        backup = Path(self.temp.name) / "backup.sqlite3"
        self.store.backup(backup)
        self.assertEqual(
            Store(backup).export(self.case)["records"],
            self.store.export(self.case)["records"],
        )
        with self.assertRaises(ValueError):
            self.store.backup(backup)
        with sqlite3.connect(backup) as con:
            con.execute("PRAGMA user_version=999")
        con.close()
        with self.assertRaises(ValueError):
            Store(backup)

    def test_case_round_trip_retains_ids_links_citations_and_history(self):
        _, document = self.source_document()
        claim = self.store.write(
            self.case,
            RecordWrite(
                kind="claim",
                title="Fixture claim",
                document_id=document["id"],
                excerpt="a proposal",
                locator="Sentence 1",
            ),
        )
        self.store.write(
            self.case,
            RecordWrite(
                kind="note",
                title="Assessment",
                body="A competing interpretation remains possible.",
                links=[claim["id"]],
            ),
        )
        bundle = self.store.export(self.case)
        restored = Store(Path(self.temp.name) / "restored.sqlite3")
        self.assertEqual(restore_case(restored, bundle), self.case)
        actual = restored.export(self.case)
        for key in ("case", "records", "relationships", "revisions"):
            self.assertEqual(actual[key], bundle[key])
        self.assertEqual(
            restored.get(claim["id"])["backlinks"][0]["title"], "Assessment"
        )
        with self.assertRaises(Conflict):
            restore_case(restored, bundle)

    def test_invalid_import_is_rejected_without_partial_case(self):
        self.source_document()
        bundle = self.store.export(self.case)
        for mutate in ("link", "history", "url"):
            invalid = deepcopy(bundle)
            if mutate == "link":
                invalid["relationships"].append(
                    {"source": "missing", "target": "missing", "relation": "references"}
                )
            elif mutate == "history":
                invalid["revisions"] = []
            else:
                invalid["records"][0]["url"] = "javascript:alert(1)"
            clean = Store(Path(self.temp.name) / (mutate + ".sqlite3"))
            with self.assertRaises(ValueError):
                restore_case(clean, invalid)
            self.assertEqual(clean.cases(), [])

    def test_public_training_case_is_fictional_and_round_trips(self):
        fixture = read_json(ROOT / "examples/training-case.json")
        self.assertEqual(len(fixture["records"]), 8)
        self.assertEqual(
            {r["kind"] for r in fixture["records"]},
            {"source", "document", "claim", "note", "actor", "event", "theme"},
        )
        self.assertTrue(
            all(
                r["provenance"]["synthetic"] is True
                and r["provenance"]["real_world_evidence"] is False
                for r in fixture["records"]
            )
        )
        restore_case(self.store, fixture)
        restored = self.store.export(fixture["case"]["id"])
        for key in ("case", "records", "relationships", "revisions"):
            self.assertEqual(restored[key], fixture[key])

    def test_import_rejects_forged_citation_identity_url_publisher_and_dates(self):
        fixture = read_json(ROOT / "examples/training-case.json")
        for field, value in [
            ("document_id", "another-document"),
            ("document_url", "https://example.org/forged"),
            ("source_id", "another-publisher"),
            ("published_on", "1900-01-01"),
            ("reviewed_on", "1900-01-01"),
        ]:
            invalid = deepcopy(fixture)
            for row in invalid["records"] + invalid["revisions"]:
                if row["kind"] == "claim":
                    row["citation_provenance"][field] = value
            clean = Store(Path(self.temp.name) / (field + ".sqlite3"))
            with self.subTest(field=field), self.assertRaises(ValueError):
                restore_case(clean, invalid)
            self.assertEqual(clean.cases(), [])

    def test_public_import_is_repeatable_without_overwriting_analyst_edits(self):
        self.assertTrue(import_public(self.store, ROOT))
        imported = self.store.get("public-source-ocha")
        self.store.write(
            imported["case_id"],
            RecordWrite(kind="source", title="My annotation", url=imported["url"]),
            imported["id"],
            imported["revision"],
        )
        self.assertFalse(import_public(self.store, ROOT))
        self.assertEqual(self.store.get(imported["id"])["title"], "My annotation")
        bundle = self.store.export("public-syria-research")
        self.assertEqual(sum(r["kind"] == "source" for r in bundle["records"]), 39)
        self.assertFalse(
            any(r["kind"] == "claim" for r in bundle["records"]),
            "Do not invent exact source excerpts for old paraphrases",
        )

    def test_private_api_auth_csrf_cookies_and_logout(self):
        app = create_app(Settings(self.path, TEST_KEY, False))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/cases").status_code, 401)
            self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
            self.assertEqual(
                client.post("/api/session", json={"access_key": TEST_KEY}).status_code,
                403,
            )
            result = client.post(
                "/api/session",
                json={"access_key": TEST_KEY},
                headers={"X-Desk-Request": "1"},
            )
            self.assertIn("HttpOnly", result.headers["set-cookie"])
            self.assertIn("SameSite=strict", result.headers["set-cookie"])
            self.assertEqual(client.get("/api/cases").status_code, 200)
            self.assertEqual(
                client.post("/api/cases", json={"title": "Blocked CSRF"}).status_code,
                403,
            )
            self.assertEqual(
                client.get("/api/cases").headers["cache-control"], "no-store"
            )
            client.delete("/api/session", headers={"X-Desk-Request": "1"})
            self.assertEqual(client.get("/api/cases").status_code, 401)

    def test_api_error_contract_limits_and_conflict(self):
        with TestClient(create_app(Settings(self.path, TEST_KEY, False))) as client:
            headers = {"X-Desk-Request": "1"}
            client.post("/api/session", json={"access_key": TEST_KEY}, headers=headers)
            bad = client.post(
                f"/api/cases/{self.case}/records",
                json={"kind": "note", "title": "", "unexpected": "secret"},
                headers=headers,
            )
            self.assertEqual(bad.status_code, 422)
            self.assertNotIn("secret", bad.text)
            url = client.post(
                f"/api/cases/{self.case}/records",
                json={
                    "kind": "source",
                    "title": "Private URL",
                    "url": "http://127.0.0.1/",
                },
                headers=headers,
            )
            self.assertEqual(url.status_code, 422)
            self.assertEqual(
                client.get("/api/cases/x/records?limit=999").status_code, 422
            )
            record = client.post(
                f"/api/cases/{self.case}/records",
                json={"kind": "note", "title": "Note"},
                headers=headers,
            ).json()
            value = {"kind": "note", "title": "Edited", "revision": record["revision"]}
            self.assertEqual(
                client.put(
                    "/api/records/" + record["id"], json=value, headers=headers
                ).status_code,
                200,
            )
            conflict = client.put(
                "/api/records/" + record["id"], json=value, headers=headers
            )
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(
                client.post(
                    "/api/cases", content="x" * 262145, headers=headers
                ).status_code,
                413,
            )
            self.assertEqual(client.get("/../../pyproject.toml").status_code, 404)
            self.assertEqual(
                client.get("/api/fetch?url=http://169.254.169.254").status_code, 404
            )

    def test_fail_closed_and_login_throttling(self):
        with self.assertRaises(ValueError):
            create_app(Settings(self.path, ""))
        with self.assertRaises(ValueError):
            create_app(Settings(self.path, TEST_KEY, allowed_hosts=("*",)))
        with TestClient(create_app(Settings(self.path, TEST_KEY, False))) as client:
            for _ in range(10):
                self.assertEqual(
                    client.post(
                        "/api/session",
                        json={"access_key": "wrong"},
                        headers={"X-Desk-Request": "1"},
                    ).status_code,
                    401,
                )
            self.assertEqual(
                client.post(
                    "/api/session",
                    json={"access_key": TEST_KEY},
                    headers={"X-Desk-Request": "1"},
                ).status_code,
                429,
            )


if __name__ == "__main__":
    unittest.main()
