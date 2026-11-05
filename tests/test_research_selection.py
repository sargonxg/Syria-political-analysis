"""Cross-tool selection boundaries, independent of provider network availability."""

import json
import unittest
from copy import deepcopy

from syria_analysis.research_selection import (
    MAX_BYTES,
    load_selection,
    make_selection,
    selection_bytes,
    validate_selection,
)


def dataset():
    return {
        "id": "fixture-dataset",
        "title": "Synthetic test data",
        "version": "test",
        "publisher": "Test fixture",
        "url": "https://example.org/test-data",
        "license": "CC0 test fixture",
        "sha256": "a" * 64,
    }


def record(i=1):
    return {
        "id": f"test:{i}",
        "kind": "conflict_event",
        "dataset_id": "fixture-dataset",
        "label": "Synthetic test record",
        "country_code": "SY",
        "date_start": "2020-02-29",
        "date_end": "2020-03-01",
        "source_locator": f"Synthetic fixture row {i}",
        "attributes": {
            "id": str(i),
            "zero": 0,
            "missing": None,
            "raw": "<b>literal</b>",
        },
    }


def pack(rows=None, **kwargs):
    return make_selection(
        [record()] if rows is None else rows,
        [dataset()],
        created_at="2026-11-05T12:00:00Z",
        **kwargs,
    )


class SelectionTests(unittest.TestCase):
    def test_shared_cross_language_contract(self):
        from pathlib import Path

        fixture = Path(__file__).parent / "fixtures/research-selection-contract.json"
        for case in json.loads(fixture.read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(not validate_selection(case["pack"]), case["valid"])

    def test_zero_null_and_literal_text_preserved(self):
        value = pack()
        self.assertEqual(validate_selection(value), [])
        self.assertEqual(load_selection(selection_bytes(value)), value)
        self.assertEqual(value["records"][0]["attributes"]["zero"], 0)
        self.assertIsNone(value["records"][0]["attributes"]["missing"])
        self.assertEqual(value["records"][0]["attributes"]["raw"], "<b>literal</b>")

    def test_export_limit_reports_exact_omissions(self):
        rows = [record(i) for i in range(350)]
        value = pack(rows, limit=17)
        self.assertEqual(
            value["counts"],
            {
                "matched": 350,
                "exported": 17,
                "limit": 17,
                "truncated": True,
            },
        )
        self.assertEqual(
            [r["id"] for r in value["records"]], [r["id"] for r in rows[:17]]
        )
        self.assertEqual(len(rows), 350, "Export must not mutate the source collection")

    def test_size_limit_counts_multibyte_utf8(self):
        rows = [record(i) for i in range(200)]
        for row in rows:
            row["attributes"]["wide"] = "語" * 7000
        value = pack(rows)
        self.assertLessEqual(len(selection_bytes(value)), MAX_BYTES)
        self.assertLess(value["counts"]["exported"], 200)
        self.assertTrue(value["counts"]["truncated"])

    def test_unknown_native_format_refused(self):
        value = pack()
        value["format"] = "tacitus-uploaded-knowledge-context/1"
        self.assertTrue(validate_selection(value))

    def test_duplicate_ids_or_unresolved_sources_refused(self):
        value = pack()
        duplicate = deepcopy(value)
        duplicate["records"].append(deepcopy(duplicate["records"][0]))
        duplicate["counts"].update(matched=2, exported=2)
        self.assertTrue(validate_selection(duplicate))
        value["records"][0]["dataset_id"] = "missing"
        self.assertTrue(validate_selection(value))

    def test_false_or_reversed_dates_refused(self):
        for start, end in [("2021-02-29", "2021-03-01"), ("2020-03-01", "2020-02-29")]:
            value = pack()
            value["records"][0].update(date_start=start, date_end=end)
            self.assertTrue(validate_selection(value))

    def test_fabricated_counts_and_unlabelled_truncation_refused(self):
        for changes in (
            {"matched": 0},
            {"exported": 2},
            {"truncated": True},
            {"limit": 0},
        ):
            value = pack()
            value["counts"].update(changes)
            self.assertTrue(validate_selection(value))

    def test_unsafe_source_metadata_or_nested_attributes_refused(self):
        for url in [
            "http://example.org/",
            "https://u:p@example.org/",
            "https://[broken/",
            "https://example.org/has whitespace",
        ]:
            value = pack()
            value["datasets"][0]["url"] = url
            self.assertTrue(validate_selection(value))

        for primitive in [float("nan"), float("inf"), 10**500, {"nested": "field"}]:
            value = pack()
            value["records"][0]["attributes"]["bad"] = primitive
            self.assertTrue(validate_selection(value))

    def test_invalid_timezone_is_not_silently_normalized(self):
        value = pack()
        value["created_at"] = "2026-11-05T12:00:00+01:60"
        self.assertTrue(validate_selection(value))

    def test_oversized_or_deep_input_refused(self):
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            load_selection(b" " * (MAX_BYTES + 1))
        value = pack()
        value["filters"] = {"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}}
        self.assertTrue(validate_selection(value))

    def test_blank_question_and_notes_are_not_generated(self):
        value = pack([])
        self.assertEqual(value["question"], "")
        self.assertEqual(
            value["notes"], {"assessment": "", "alternatives": "", "gaps": ""}
        )
        self.assertEqual(value["counts"]["matched"], 0)
        self.assertFalse(value["counts"]["truncated"])

    def test_bom_and_crlf_import_is_valid(self):
        payload = (
            b"\xef\xbb\xbf"
            + json.dumps(pack(), indent=2).replace("\n", "\r\n").encode()
        )
        self.assertEqual(load_selection(payload), pack())


if __name__ == "__main__":
    unittest.main()
