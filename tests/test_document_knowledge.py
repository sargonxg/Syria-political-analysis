"""Source fidelity, context dependency, database integrity and safe viewer tests."""

import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from syria_analysis.document_knowledge import (
    evaluate_selection,
    jsonld,
    normalize_federal_register,
    read_json,
    reopen,
    search,
    select_context,
    validate_model,
    write_database,
)
from syria_analysis.document_knowledge_view import viewer

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "data/policy-case/eo-14179"


class DocumentKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.text = (CASE / "document.txt").read_text(encoding="utf-8")
        self.model = read_json(CASE / "model.json")
        self.receipt = read_json(CASE / "receipt.json")
        self.source = {k: self.receipt[k] for k in ["title", "uri", "published_on"]}

    def test_full_capture_and_normalization_are_reproducible(self):
        raw = (CASE / "source.html").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.receipt["sha256"])
        self.assertEqual(normalize_federal_register(raw), self.text)
        self.assertEqual(
            hashlib.sha256(self.text.encode()).hexdigest(),
            self.receipt["normalized_sha256"],
        )
        self.assertIn("Sec. 6.", self.text)
        self.assertIn("January 23, 2025.", self.text)
        self.assertNotIn("Executive Order 14180", self.text)
        paragraphs, _ = validate_model(self.text, self.source, self.model)
        self.assertEqual(len(paragraphs), 17)
        for p in paragraphs:
            self.assertEqual(
                self.text.encode()[p["span"]["start"] : p["span"]["end"]],
                p["text"].encode(),
            )

    def test_task_selection_keeps_qualifications_and_never_promotes_outcomes(self):
        selection = select_context(self.text, self.source, self.model, "action-plan")
        claims = {a["id"]: a for a in selection["context"]["assertions"]}
        self.assertIn("appropriations-limit", claims)
        self.assertIn("authority-limit", claims)
        self.assertIn("policy-objective", claims)
        self.assertEqual(
            claims["action-plan"]["addressed_to_ids"], ["apst", "advisor", "apnsa"]
        )
        self.assertIn("within 180 days", claims["action-plan"]["statement"])
        self.assertTrue(
            all(
                a["implementation_established"] is False
                and a["human_review_recorded"] is False
                for a in claims.values()
            )
        )
        self.assertEqual(len(selection["prompt"].encode()), selection["prompt_bytes"])
        self.assertLessEqual(selection["prompt_bytes"], selection["max_bytes"])
        with self.assertRaisesRegex(ValueError, "No dependency was silently removed"):
            select_context(self.text, self.source, self.model, "action-plan", 1024)

    def test_comparison_reports_the_shorter_but_incomplete_seed_baseline(self):
        result = evaluate_selection(self.text, self.source, self.model, "action-plan")
        self.assertEqual(result["selected_missing_required_ids"], [])
        self.assertIn("appropriations-limit", result["seed_only_missing_required_ids"])
        self.assertLess(
            result["seed_only_prompt_bytes"], result["selected_prompt_bytes"]
        )
        self.assertLess(
            result["selected_prompt_bytes"], result["full_structured_prompt_bytes"]
        )
        self.assertGreater(result["selected_prompt_bytes"], result["source_text_bytes"])
        self.assertIs(result["answer_quality_measured"], False)
        self.assertIs(result["model_executed"], False)

    def test_invalid_or_cyclic_claims_refuse(self):
        patches = [
            lambda m: m["assertions"][0].update(
                source_verb="A VERB ABSENT FROM THE SOURCE"
            ),
            lambda m: m["assertions"][0].update(implementation_established=True),
            lambda m: m["assertions"][0].update(paragraph_ids=["p999"]),
            lambda m: m["assertions"][0].update(addressed_to_ids=["invented"]),
            lambda m: m["assertions"][0].update(requires=["policy-objective"]),
            lambda m: m["entities"][0].update(type="InventedClass"),
        ]
        for patch in patches:
            m = copy.deepcopy(self.model)
            patch(m)
            with self.assertRaises(ValueError):
                validate_model(self.text, self.source, m)
        m = copy.deepcopy(self.model)
        m["assertions"][0]["requires"] = ["action-plan"]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            validate_model(self.text, self.source, m)
        with self.assertRaisesRegex(ValueError, "Unknown task"):
            select_context(self.text, self.source, self.model, "missing")
        with self.assertRaises(ValueError):
            select_context(self.text, self.source, self.model, "action-plan", True)

    def test_readonly_database_and_search_preserve_every_text_block(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "case.sqlite3"
            write_database(path, self.text, self.source, self.model)
            before = path.read_bytes()
            text, source, model = reopen(path)
            self.assertEqual(
                (text, source, model), (self.text, self.source, self.model)
            )
            rows = search(path, "availability appropriations")
            self.assertEqual([r["id"] for r in rows], ["p013"])
            self.assertEqual(path.read_bytes(), before)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                write_database(path, self.text, self.source, self.model)
            with self.assertRaises(ValueError):
                search(path, "appropriations", 51)
            with self.assertRaises(ValueError):
                search(path, "*")
            self.assertEqual(search(path, "x'); DROP TABLE document;--"), [])

    def test_database_tampering_and_projection_drift_refuse(self):
        edits = [
            "UPDATE document SET source_json=replace(source_json,'Removing','Invented')",
            "UPDATE paragraph SET text='altered' WHERE id='p013'",
            "UPDATE paragraph_search SET text='altered' WHERE id='p013'",
            "DELETE FROM dependency WHERE requires_id='appropriations-limit'",
            "UPDATE document SET text='altered'",
        ]
        with tempfile.TemporaryDirectory() as temp:
            for number, sql in enumerate(edits):
                path = Path(temp) / f"{number}.sqlite3"
                write_database(path, self.text, self.source, self.model)
                with sqlite3.connect(path) as db:
                    db.execute(sql)
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    reopen(path)

    def test_supplied_database_views_have_an_execution_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "case.sqlite3"
            write_database(path, self.text, self.source, self.model)
            with sqlite3.connect(path) as db:
                db.executescript("""ALTER TABLE document RENAME TO original_document;
                    CREATE VIEW document AS SELECT * FROM original_document
                    WHERE (WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1000000000) SELECT sum(x) FROM n)>0;""")
            with self.assertRaisesRegex(sqlite3.DatabaseError, "interrupted"):
                reopen(path)

    def test_jsonld_reifies_claims_without_asserting_political_triples(self):
        graph = jsonld(self.text, self.source, self.model)
        claims = [x for x in graph["@graph"] if isinstance(x["@type"], list)]
        self.assertEqual(len(claims), 8)
        self.assertTrue(
            all(
                "rdf:Statement" in c["@type"]
                and c["case:reviewState"] == "needs_source_check"
                for c in claims
            )
        )
        self.assertTrue(
            all("rdf:predicate" in c and "prov:wasDerivedFrom" in c for c in claims)
        )
        self.assertFalse(any("case:directs" in row for row in graph["@graph"]))

    def test_hostile_source_and_annotations_render_as_text(self):
        model = copy.deepcopy(self.model)
        attack = "</script><script>window.injected=true</script>"
        model["assertions"][0]["statement"] = attack
        contexts = {
            t["id"]: select_context(self.text, self.source, model, t["id"])
            for t in model["tasks"]
        }
        evaluations = {
            t["id"]: evaluate_selection(self.text, self.source, model, t["id"])
            for t in model["tasks"]
        }
        page = viewer(self.text, self.receipt, model, contexts, evaluations)
        self.assertNotIn(attack, page)
        self.assertIn("&lt;/script&gt;", page)
        self.assertIn("connect-src 'none'", page)
        self.assertIn("sha256-", page)

    def test_cli_build_reopen_and_write_refusals(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "case"
            command = [sys.executable, str(ROOT / "scripts/build_policy_case.py")]
            run = lambda extra: subprocess.run(
                command + extra, check=False, cwd=ROOT, capture_output=True, text=True
            )
            first = run(["--output", str(out)])
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(json.loads(first.stdout)["reopen_verified"])
            self.assertEqual(run(["--output", str(out)]).returncode, 2)
            result = run(
                ["--database", str(out / "research.sqlite3"), "--task", "review"]
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("revocation-review", result.stdout)
            if os.name != "nt":
                alias = Path(temp) / "alias"
                alias.symlink_to(out, target_is_directory=True)
                self.assertEqual(run(["--output", str(alias / "new")]).returncode, 2)


if __name__ == "__main__":
    unittest.main()
