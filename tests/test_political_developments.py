from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from syria_analysis.political_developments import (
    MAX_BYTES,
    build_browser,
    build_study,
    read_json,
    select_developments,
    validate_selection,
    validate_study,
)

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = Path("/workspace/research/political-evidence-refinement/artifacts")


class PoliticalDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.study = build_study(ROOT)

    def bad(self, mutate):
        study = deepcopy(self.study)
        mutate(study)
        with self.assertRaises(ValueError):
            validate_study(study)

    def test_three_source_qualified_political_acts_remain_separate(self):
        self.assertTrue(validate_study(self.study))
        rows = self.study["political"]["developments"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["development_kind"] for row in rows},
            {"adoption", "meeting", "announced_programme"},
        )
        for row in rows:
            self.assertEqual(row["record_type"], "political_development")
            self.assertIsNone(row["coordinates"])
            self.assertEqual(row["conflict_observation_links"], [])
            self.assertFalse(row["structured_act"]["policy_objectives_implemented"])
            self.assertFalse(row["structured_act"]["current_conditions_established"])
            self.assertFalse(row["review"]["human_review_recorded"])

    def test_unknown_event_day_is_not_replaced_with_publication_day(self):
        row = self.study["political"]["developments"][2]
        source = self.study["political"]["sources"][2]
        self.assertEqual(source["published_on"], "2026-07-30")
        self.assertEqual(row["event_time"]["precision"], "unknown")
        self.assertIsNone(row["event_time"]["start"])
        self.assertIsNone(row["event_time"]["end"])
        self.assertIn("No event day is manufactured", row["event_time"]["basis"])
        self.assertEqual(row["planned_period"]["kind"], "source_reported_plan")
        self.assertEqual(row["planned_period"]["end"], "2028-07")
        self.bad(
            lambda s: s["political"]["developments"][2]["event_time"].update(
                start="2026-07-30"
            )
        )

    def test_relative_meeting_date_basis_is_explicit(self):
        row = self.study["political"]["developments"][1]
        self.assertEqual(row["event_time"]["start"], "2019-09-30")
        self.assertEqual(date.fromisoformat(row["event_time"]["start"]).weekday(), 0)
        self.assertIn("on Monday", row["event_time"]["basis"])
        self.assertIn(
            "not a generic publication-to-event-date substitution",
            row["event_time"]["basis"],
        )
        self.assertEqual(
            row["structured_act"]["actor"], "UN Special Envoy Geir O. Pedersen"
        )

    def test_primary_adoption_header_is_distinct_from_implementation(self):
        source = self.study["political"]["sources"][0]
        quote = source["excerpts"][0]
        self.assertEqual(
            quote["text"],
            "Adopted by the Security Council at its 7588th meeting, on 18 December 2015",
        )
        self.assertEqual(
            source["capture"]["sha256"],
            "932c9614e588e910c5c23a82b4df67679aba7bbe2c47ef2edd1d02970f0faa62",
        )
        self.assertIn(
            "not thereby established as implemented",
            self.study["political"]["developments"][0]["qualifications"][0],
        )

    def test_excerpt_digests_word_bounds_and_source_rights(self):
        for source in (
            self.study["political"]["sources"] + self.study["media"]["sources"]
        ):
            self.assertFalse(source["capture"]["full_document_redistributed"])
            self.assertIn("not relicensed", source["rights_note"])
            for quote in source["excerpts"]:
                self.assertEqual(
                    quote["sha256"], hashlib.sha256(quote["text"].encode()).hexdigest()
                )
                self.assertLessEqual(len(quote["text"].split()), 160)
                self.assertTrue(quote["locator"])
                self.assertEqual(quote["text_kind"], "exact_excerpt")
        self.bad(
            lambda s: s["political"]["sources"][0]["excerpts"][0].update(
                text="Invented quotation"
            )
        )
        self.bad(
            lambda s: s["political"]["sources"][0].update(
                article_html="<html>full article</html>"
            )
        )
        self.bad(
            lambda s: s["political"]["sources"][0]["capture"].update(
                full_document_redistributed=True
            )
        )

    def test_promoted_review_outcome_or_conflict_links_are_rejected(self):
        for mutate in (
            lambda s: s["political"]["sources"][0].update(human_review_recorded=True),
            lambda s: s["political"]["developments"][0]["review"].update(
                human_review_recorded=True
            ),
            lambda s: s["political"]["developments"][0]["structured_act"].update(
                policy_objectives_implemented=True
            ),
            lambda s: s["political"]["developments"][0]["structured_act"].update(
                current_conditions_established=True
            ),
            lambda s: s["political"]["developments"][0].update(
                record_type="conflict_event"
            ),
            lambda s: s["political"]["developments"][0].update(
                coordinates=[36.2, 33.5]
            ),
            lambda s: s["political"]["developments"][0].update(
                conflict_observation_links=["caused-violence"]
            ),
        ):
            self.bad(mutate)

    def test_wrong_source_excerpt_and_duplicate_ids_are_rejected(self):
        self.bad(
            lambda s: s["political"]["developments"][0]["evidence"][0].update(
                excerpt_id="committee-briefing-lead"
            )
        )
        self.bad(
            lambda s: s["political"]["sources"][1].update(
                id=s["political"]["sources"][0]["id"]
            )
        )
        self.bad(
            lambda s: s["political"]["developments"][1].update(
                id=s["political"]["developments"][0]["id"]
            )
        )

    def test_real_dates_order_and_plan_precision(self):
        self.bad(
            lambda s: s["political"]["developments"][0]["event_time"].update(
                start="2015-02-30"
            )
        )
        self.bad(
            lambda s: s["political"]["developments"][0]["event_time"].update(
                end="2015-12-17"
            )
        )
        self.bad(
            lambda s: s["political"]["sources"][0].update(published_on="2015-13-01")
        )
        self.bad(
            lambda s: s["political"]["sources"][1].update(
                published_at="2019-10-01T12:00:00Z"
            )
        )
        self.bad(
            lambda s: s["political"]["developments"][2]["planned_period"].update(
                end="2026-13"
            )
        )
        self.bad(
            lambda s: s["political"]["developments"][2]["planned_period"].update(
                end="2020-01"
            )
        )

    def test_public_urls_are_not_credentials_or_private_ip_references(self):
        for url in (
            "http://example.org/item",
            "https://user:password@example.org/item",
            "https://127.0.0.1/item",
            "https://[::1]/item",
            "https://localhost/item",
            "https://example.local/item",
            "file:///tmp/private",
        ):
            with self.subTest(url=url):
                self.bad(
                    lambda s, url=url: s["political"]["sources"][0].update(url=url)
                )

    def test_media_compares_different_genres_dates_and_retains_counterexample(self):
        media = self.study["media"]
        self.assertEqual(
            [s["source_kind"] for s in media["sources"]], ["news_report", "analysis"]
        )
        self.assertEqual(
            [s["published_on"] for s in media["sources"]], ["2015-12-18", "2015-12-19"]
        )
        self.assertEqual(
            {a["kind"] for a in media["annotations"]},
            {"observable_text_feature", "analyst_interpretation"},
        )
        self.assertIn(
            "disagreements remain", media["sources"][0]["excerpts"][2]["text"]
        )
        self.assertTrue(
            any("not a representative study" in item for item in media["boundaries"])
        )
        self.assertFalse(media["lineage"]["independent_reporting_verified"])
        self.assertFalse(media["lineage"]["upstream_dependence_assessed"])
        self.bad(
            lambda s: s["media"]["lineage"].update(independent_reporting_verified=True)
        )
        self.bad(
            lambda s: s["media"]["annotations"][0].update(kind="publisher_bias_finding")
        )
        self.bad(lambda s: s["media"].update(bias_score=80))

    def test_selection_is_deterministic_and_preserves_source_objects(self):
        before = deepcopy(self.study)
        ids = [self.study["political"]["developments"][0]["id"]]
        packet = select_developments(self.study, ids, "What act is documented?")
        self.assertEqual(
            packet, select_developments(self.study, ids, "What act is documented?")
        )
        self.assertEqual(self.study, before)
        self.assertEqual(packet["records"], [before["political"]["developments"][0]])
        self.assertEqual(len(packet["selection"]["omitted_record_ids"]), 2)
        self.assertEqual(len(packet["sources"]), 1)
        self.assertEqual(
            [q["id"] for q in packet["sources"][0]["excerpts"]],
            ["2254-adoption-header"],
        )
        self.assertEqual(len(packet["selection"]["omitted_excerpt_ids"]), 4)
        self.assertEqual(
            packet["sources"][0]["capture"],
            before["political"]["sources"][0]["capture"],
        )
        self.assertTrue(validate_selection(packet, self.study))

    def test_selection_normalizes_order_and_rejects_unknown_or_duplicate_ids(self):
        ids = [r["id"] for r in self.study["political"]["developments"]]
        packet = select_developments(self.study, list(reversed(ids)))
        self.assertEqual(packet["selection"]["retained_record_ids"], ids)
        for bad in ([], ["unknown"], [ids[0], ids[0]], [None], "not-an-array"):
            with self.subTest(ids=bad), self.assertRaises(ValueError):
                select_developments(self.study, bad)
        for question in ("", "   ", "x" * 2001, None):
            with self.subTest(question=question), self.assertRaises(ValueError):
                select_developments(self.study, question=question)

    def test_tampered_exports_are_not_silently_repaired(self):
        for mutate in (
            lambda p: p["records"][0]["structured_act"].update(
                policy_objectives_implemented=True
            ),
            lambda p: p["sources"][0]["excerpts"][0].update(text="Different text"),
            lambda p: p["selection"].update(omitted_record_ids=[]),
            lambda p: p.update(source_snapshot_sha256="0" * 64),
        ):
            packet = select_developments(
                self.study, [self.study["political"]["developments"][0]["id"]]
            )
            mutate(packet)
            with self.assertRaises(ValueError):
                validate_selection(packet, self.study)

    def test_bounded_json_rejects_oversize_deep_duplicate_or_nonportable_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for payload in (
                b"{",
                b"\xff",
                b" " * (MAX_BYTES + 1),
                b'{"a":1,"a":2}',
                b'{"bad":NaN}',
                b'{"bad":1e999}',
                b'{"__proto__":{}}',
                b"[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]",
                ('{"n":' + "1" * 400 + "}").encode(),
            ):
                path.write_bytes(payload)
                with self.subTest(payload=payload[:50]), self.assertRaises(ValueError):
                    read_json(path)

    def test_schema_accepts_every_export_form(self):
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError:
            self.skipTest("jsonschema is an optional development dependency")
        schema = json.loads(
            (ROOT / "schemas/political_developments.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for value in (
            self.study,
            self.study["political"],
            self.study["media"],
            select_developments(self.study),
        ):
            with self.subTest(format=value["format"]):
                self.assertEqual(list(validator.iter_errors(value)), [])

    def test_standalone_cli_build_and_read_only_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            cmd = [
                sys.executable,
                str(ROOT / "scripts/build_political_developments.py"),
            ]
            result = subprocess.run(
                cmd + ["--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                {p.name for p in output.iterdir()},
                {
                    "study.json",
                    "developments.json",
                    "media-comparison.json",
                    "selection.json",
                },
            )
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            result = subprocess.run(
                cmd
                + [
                    "--validate",
                    str(output / "selection.json"),
                    "--output",
                    str(output / "absent"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((output / "absent").exists())
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            (output / "invalid.json").write_text("[]")
            result = subprocess.run(
                cmd + ["--validate", str(output / "invalid.json")],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_optional_html_build_and_validation_do_not_activate_services(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "json"
            html = root / "browser/index.html"
            command = [
                sys.executable,
                str(ROOT / "scripts/build_political_developments.py"),
            ]
            built = subprocess.run(
                command + ["--output", str(output), "--html", str(html)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertTrue(html.is_file())
            self.assertEqual(
                {p.name for p in html.parent.iterdir()},
                {"index.html", "political-study.js", "political-study.css"},
            )
            untouched = root / "must-not-exist/index.html"
            checked = subprocess.run(
                command
                + [
                    "--validate",
                    str(output / "selection.json"),
                    "--html",
                    str(untouched),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertFalse(untouched.parent.exists())

    def test_static_browser_has_self_only_code_and_prepared_validated_packets(self):
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.scripts = []
                self.in_data = False
                self.data = ""

            def handle_starttag(self, tag, attrs):
                if tag == "script":
                    props = dict(attrs)
                    self.scripts.append(props)
                    self.in_data = props.get("id") == "political-study-data"

            def handle_endtag(self, tag):
                if tag == "script":
                    self.in_data = False

            def handle_data(self, value):
                if self.in_data:
                    self.data += value

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "politics/index.html"
            self.assertEqual(build_browser(self.study, output), output)
            self.assertTrue((output.parent / "political-study.js").exists())
            self.assertTrue((output.parent / "political-study.css").exists())
            page = output.read_text(encoding="utf-8")
            self.assertIn("script-src 'self'", page)
            self.assertIn("connect-src 'none'", page)
            self.assertNotIn("'unsafe-inline'", page)
            parser = Scripts()
            parser.feed(page)
            executable = [
                props
                for props in parser.scripts
                if props.get("type") != "application/json"
            ]
            self.assertEqual(
                executable, [{"defer": None, "src": "./political-study.js"}]
            )
            payload = json.loads(parser.data)
            self.assertEqual(payload["study"], self.study)
            self.assertEqual(
                set(payload["selections"]),
                {row["id"] for row in self.study["political"]["developments"]},
            )
            for identifier, packet in payload["selections"].items():
                self.assertEqual(packet, select_developments(self.study, [identifier]))
                self.assertTrue(validate_selection(packet, self.study))
            javascript = (output.parent / "political-study.js").read_text(
                encoding="utf-8"
            )
            for unsafe in (
                ".innerHTML",
                ".outerHTML",
                "insertAdjacentHTML",
                "eval(",
                "new Function",
                "fetch(",
            ):
                self.assertNotIn(unsafe, javascript)

    def test_static_browser_escapes_script_terminators_without_changing_source_text(
        self,
    ):
        study = deepcopy(self.study)
        attack = "</script><script>globalThis.injected=true</script><img src=x onerror=alert(1)> & \u2028 \u2029"
        quote = study["political"]["sources"][0]["excerpts"][0]
        quote["text"] = attack
        quote["sha256"] = hashlib.sha256(attack.encode()).hexdigest()
        study["political"]["developments"][0]["title"] = attack
        self.assertTrue(validate_study(study))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "index.html"
            build_browser(study, output)
            page = output.read_text(encoding="utf-8")
            self.assertNotIn(attack, page)
            self.assertNotIn("<img src=x", page)
            self.assertIn("\\u003c/script\\u003e", page)
            match = page.split(
                '<script id="political-study-data" type="application/json">', 1
            )[1].split("</script>", 1)[0]
            restored = json.loads(match)
            self.assertEqual(
                restored["study"]["political"]["sources"][0]["excerpts"][0]["text"],
                attack,
            )
            self.assertEqual(
                restored["selections"][study["political"]["developments"][0]["id"]][
                    "records"
                ][0]["title"],
                attack,
            )

    def test_static_browser_rejects_invalid_input_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "absent/index.html"
            bad = deepcopy(self.study)
            bad["political"]["developments"][0]["review"]["human_review_recorded"] = (
                True
            )
            with self.assertRaises(ValueError):
                build_browser(bad, output)
            self.assertFalse(output.parent.exists())
            with self.assertRaises(ValueError):
                build_browser(self.study, Path(directory) / "absent/index.txt")
            self.assertFalse(output.parent.exists())

    def test_optional_captured_quote_fidelity(self):
        if not (CAPTURE / "bbc-2254.html").exists():
            self.skipTest(
                "Optional original captures are not redistributed in the repository"
            )

        class Paragraphs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.current = None
                self.blocks = []

            def handle_starttag(self, tag, _attrs):
                if tag == "p":
                    self.current = []

            def handle_endtag(self, tag):
                if tag == "p" and self.current is not None:
                    self.blocks.append(" ".join("".join(self.current).split()))
                    self.current = None

            def handle_data(self, value):
                if self.current is not None:
                    self.current.append(value)

        names = {
            "bbc-2254-report": "bbc-2254",
            "guardian-2254-analysis": "guardian-analysis-2254",
            "un-news-2019-committee-briefing": "un-committee-announcement",
            "un-syria-homs-programme-2026": "un-homs-programme",
        }
        for source in (
            self.study["political"]["sources"] + self.study["media"]["sources"]
        ):
            if source["id"] not in names:
                continue
            raw = (CAPTURE / (names[source["id"]] + ".html")).read_bytes()
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(), source["capture"]["sha256"]
            )
            parser = Paragraphs()
            parser.feed(raw.decode())
            flattened = " ".join(unescape(raw.decode()).split())
            for quote in source["excerpts"]:
                if quote["id"].endswith("-headline"):
                    self.assertIn(quote["text"], flattened)
                else:
                    self.assertIn(quote["text"], "\n".join(parser.blocks))


if __name__ == "__main__":
    unittest.main()
