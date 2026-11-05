import json
import tempfile
import tomllib
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from syria_analysis import __version__
from syria_analysis.cli import main
from syria_analysis.core import load_workspace
from syria_analysis.media_assessment import comparison, markdown, validate_assessment

ROOT = Path(__file__).resolve().parents[1]


class MediaAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.workspace = load_workspace(ROOT)
        self.pack = comparison(
            self.workspace, "syria-direct", "sana", "How is the selected claim framed?"
        )

    def test_release_metadata_agrees_without_changing_the_assessment_contract(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        manifest = json.loads((ROOT / "data/manifest.json").read_text())
        self.assertEqual(__version__, project["project"]["version"])
        self.assertEqual(__version__, manifest["toolkit_version"])
        self.assertEqual(self.pack["format"], "media-framing-assessment/1")

    def test_schema_preserves_original_profiles_without_rating_or_false_review(self):
        schema = json.loads((ROOT / "schemas/media_assessment.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(self.pack)
        self.assertTrue(validate_assessment(self.pack))
        self.assertFalse(self.pack["human_review_recorded"])
        index = {p["id"]: p for p in self.workspace["sources"]}
        for profile in self.pack["source_profiles"]:
            self.assertEqual(profile, index[profile["id"]])
        self.assertNotIn("bias_score", self.pack)
        self.assertEqual(self.pack["assessment"]["status"], "not_assessed")

    def test_unknown_and_identical_sources_or_empty_question_are_rejected(self):
        for left, right, question in [
            ("missing", "sana", "Q"),
            ("sana", "sana", "Q"),
            ("sana", "syria-direct", " "),
            ("sana", "syria-direct", "x" * 2001),
        ]:
            with self.assertRaises(ValueError):
                comparison(self.workspace, left, right, question)

    def test_report_order_cannot_move_quotations_to_another_publisher(self):
        self.pack["reports"][0]["evidence"]["framing"]["passage"] = (
            "Synthetic passage A."
        )
        self.pack["reports"][1]["evidence"]["framing"]["passage"] = (
            "Synthetic passage B."
        )
        self.pack["reports"].reverse()
        output = markdown(self.pack)
        a = output.index("Synthetic passage A.")
        b = output.index("Synthetic passage B.")
        self.assertLess(output.index("## Syria Direct"), a)
        self.assertLess(
            a, output.index("## " + self.pack["source_profiles"][1]["name"])
        )
        self.assertGreater(
            b, output.index("## " + self.pack["source_profiles"][1]["name"])
        )

    def test_invalid_provenance_and_false_review_are_rejected(self):
        for field, value in [
            ("source_id", "invented"),
            ("url", "http://127.0.0.1/private"),
            ("url", "javascript:alert(1)"),
        ]:
            pack = deepcopy(self.pack)
            pack["reports"][0][field] = value
            with self.assertRaises(ValueError):
                validate_assessment(pack)
        self.pack["human_review_recorded"] = True
        with self.assertRaises(ValueError):
            validate_assessment(self.pack)

    def test_cli_and_markdown_keep_assessment_separate_from_selected_passages(self):
        self.pack["reports"][0]["evidence"]["framing"]["passage"] = "Synthetic passage."
        self.pack["reports"][0]["evidence"]["framing"]["note"] = "My reading of it."
        self.pack["assessment"]["interpretation"] = "A provisional interpretation."
        output = markdown(self.pack)
        self.assertIn("Selected passage: Synthetic passage.", output)
        self.assertIn("Analyst note: My reading of it.", output)
        self.assertIn(
            "## Analyst interpretation\n\nA provisional interpretation.", output
        )
        self.assertIn("## Alternative explanation\n\n[Not supplied]", output)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comparison.json"
            self.assertEqual(
                main(
                    [
                        "--root",
                        str(ROOT),
                        "compare-sources",
                        "--left",
                        "syria-direct",
                        "--right",
                        "sana",
                        "--question",
                        "A test question",
                        "--output",
                        str(path),
                    ]
                ),
                0,
            )
            validate_assessment(json.loads(path.read_text()))

    def test_regional_resources_have_evidence_and_explicit_access_scope(self):
        resources = json.loads((ROOT / "data/sources/resources.json").read_text())[
            "profiles"
        ]
        self.assertEqual(len(resources), 8)
        self.assertEqual(len({r["id"] for r in resources}), 8)
        for row in resources:
            self.assertTrue(row["evidence"])
            self.assertTrue(row["ingestion"])
            self.assertTrue(row["cautions"])
        sources = {p["id"]: p for p in self.workspace["sources"]}
        for identifier in ["daraj", "merip", "sjac"]:
            self.assertTrue(sources[identifier]["feeds"][0]["verified_on"])


if __name__ == "__main__":
    unittest.main()
