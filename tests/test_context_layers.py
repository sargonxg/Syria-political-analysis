import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from syria_analysis import core, countries, ontology
from syria_analysis.cli import main
from syria_analysis.context_layers import (
    assemble,
    build_explorer,
    markdown,
    validate_pack,
)

ROOT = Path(__file__).resolve().parents[1]


class ContextLayersTests(unittest.TestCase):
    def setUp(self):
        self.workspace = core.load_workspace(ROOT)
        self.country = countries.resolve(ROOT, "SY")[1]
        self.model = ontology.build_model(ROOT, ROOT, self.workspace, self.country)
        self.pack = assemble(
            self.workspace, self.model, self.country, "What does 2254 request?"
        )

    def test_schema_and_provenance_closure(self):
        schema = core.read_json(ROOT / "schemas/context_layers.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(self.pack)
        self.assertTrue(validate_pack(self.pack))
        self.assertEqual(
            sum(row["record_count"] for row in self.pack["layers"]),
            len(self.pack["records"]),
        )
        for row in self.pack["records"]:
            for did in row.get("document_ids", []):
                self.assertIn(
                    "document:" + did, {r["id"] for r in self.pack["records"]}
                )
        invalid = deepcopy(self.pack)
        invalid["edges"].append(
            {
                "source": "missing",
                "target": self.pack["records"][0]["id"],
                "relation": "test",
            }
        )
        with self.assertRaisesRegex(ValueError, "Dangling"):
            validate_pack(invalid)

    def test_preserves_source_qualified_normative_drafts(self):
        rows = [r for r in self.pack["records"] if r["id"].startswith("assertion:")]
        self.assertEqual(len(rows), len(self.model["assertions"]))
        for row, original in zip(rows, self.model["assertions"]):
            self.assertEqual(row["data"], original)
            self.assertFalse(row["data"]["modality"]["implementation_asserted"])
            self.assertFalse(row["data"]["human_review_recorded"])
            self.assertEqual(row["review_state"], "needs_source_check")
        self.assertFalse(self.pack["assessment"]["interpretation"])

    def test_cutoff_is_publication_only_with_unknown_dates_disclosed(self):
        cutoff = "2015-12-17"
        pack = assemble(
            self.workspace, self.model, self.country, "Historical reading", cutoff
        )
        included = {r["data"]["id"] for r in pack["records"] if r["kind"] == "document"}
        for doc in self.workspace["documents"]:
            published = doc.get("published_on") or (doc.get("published_at") or "")[:10]
            self.assertEqual(
                doc["id"] in included, not published or published <= cutoff
            )
            if not published:
                self.assertIn(
                    doc["id"], pack["omissions"]["unknown_publication_date_ids"]
                )
        self.assertFalse(any(r["id"].startswith("assertion:") for r in pack["records"]))
        self.assertEqual(
            len([r for r in pack["records"] if r["layer"] == "sources"]),
            len(self.workspace["sources"]),
        )
        self.assertTrue(validate_pack(pack))

    def test_invalid_inputs_and_snapshot_scope(self):
        for bad in ("", " ", "x" * 2001):
            with self.assertRaises(ValueError):
                assemble(self.workspace, self.model, self.country, bad)
        for bad in ("2015-1-1", "2015-02-30", "yesterday"):
            with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                assemble(self.workspace, self.model, self.country, "Question", bad)
        other = assemble(
            self.workspace, self.model, self.country, "A different question"
        )
        self.assertEqual(other["snapshot"], self.pack["snapshot"])

    def test_html_escapes_untrusted_script_terminators(self):
        self.pack["question"] = "</script><script>window.INJECTED=true</script>"
        with tempfile.TemporaryDirectory() as directory:
            path = build_explorer(self.pack, Path(directory) / "index.html")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(self.pack["question"], text)
            self.assertIn("\\u003c/script>", text)
            self.assertIn("connect-src 'none'", text)

    def test_markdown_separates_authored_assessment_and_citations(self):
        row = next(r for r in self.pack["records"] if r["id"].startswith("assertion:"))
        self.pack["assessment"]["selected_record_ids"] = [row["id"]]
        self.pack["assessment"]["interpretation"] = "My provisional interpretation."
        text = markdown(self.pack)
        self.assertIn(row["id"], text)
        self.assertIn("Qualification:", text)
        self.assertIn("Operative paragraph", text)
        self.assertIn(
            "## Analyst interpretation\n\nMy provisional interpretation.", text
        )
        self.assertIn("## Alternative explanation\n\n[Not supplied]", text)

    def test_empty_country_isolation_and_cli_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "data", root / "data")
            shutil.copytree(ROOT / "ontology", root / "ontology")
            self.assertEqual(
                main(
                    [
                        "--root",
                        str(root),
                        "init-country",
                        "--code",
                        "LB",
                        "--name",
                        "Lebanon",
                        "--region",
                        "Middle East",
                    ]
                ),
                0,
            )
            for fmt, suffix in [("json", "json"), ("html", "html"), ("markdown", "md")]:
                path = root / ("context." + suffix)
                self.assertEqual(
                    main(
                        [
                            "--root",
                            str(root),
                            "--country",
                            "LB",
                            "context-layers",
                            "--question",
                            "What needs research?",
                            "--format",
                            fmt,
                            "--output",
                            str(path),
                        ]
                    ),
                    0,
                )
                self.assertTrue(path.is_file())
                if fmt == "json":
                    pack = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(pack["country"]["code"], "LB")
                    # Shared schema definitions are portable; country facts are not.
                    self.assertTrue(
                        all(
                            r["kind"] in ("entity_type", "relation_definition")
                            for r in pack["records"]
                        )
                    )
                    self.assertEqual(pack["edges"], [])


if __name__ == "__main__":
    unittest.main()
