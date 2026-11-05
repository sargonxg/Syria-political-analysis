"""Country context contracts: attribution, missingness and real source limits."""

import hashlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.error import HTTPError

from syria_analysis.country_context import (
    WorldBankClient,
    build_snapshot,
    build_static_bundle,
    collect_snapshot,
    normalize_rows,
    parse_indicator_metadata,
)

CODE = "SP.POP.TOTL"


def metadata(licence="CC BY-4.0"):
    fields = {
        "IndicatorName": "Population, total",
        "Longdefinition": "Midyear population estimates, all residents.",
        "License_Type": licence,
        "License_URL": "https://datacatalog.worldbank.org/public-licenses#cc-by",
        "Periodicity": "Annual",
        "Unitofmeasure": "Unit",
        "Aggregationmethod": "Sum",
        "Source": "UN Population Division",
    }
    return {
        "source": [
            {
                "id": "2",
                "concept": [
                    {
                        "id": "Series",
                        "variable": [
                            {
                                "id": CODE,
                                "metatype": [
                                    {"id": k, "value": v} for k, v in fields.items()
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def row(year, value, status=""):
    return {
        "indicator": {"id": CODE, "value": "Population, total"},
        "country": {"id": "SY", "value": "Syrian Arab Republic"},
        "countryiso3code": "SYR",
        "date": str(year),
        "value": value,
        "unit": "",
        "decimal": 2,
        "obs_status": status,
        "footnote": "Synthetic test fixture; no real population assertion.",
    }


class FakeClient:
    """Two-page synthetic response, intentionally null bulk sourceid."""

    def __init__(self, fail_second_page=False):
        self.calls = []
        self.fail_second_page = fail_second_page

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path == "/sources/2":
            payload = [{"pages": 1}, [{"id": "2", "lastupdated": "2026-10-08"}]]
        elif path == "/country/SYR":
            payload = [
                {"pages": 1},
                [
                    {
                        "id": "SYR",
                        "iso2Code": "SY",
                        "name": "Syrian Arab Republic",
                        "region": {"id": "MEA", "value": "Middle East"},
                    }
                ],
            ]
        elif path == "/sources/2/series/" + CODE + "/metadata":
            payload = metadata()
        elif "/indicator/" in path:
            page = params["page"]
            if page == 2 and self.fail_second_page:
                raise ValueError("Synthetic interrupted pagination")
            payload = [
                {
                    "page": page,
                    "pages": 2,
                    "total": 2,
                    "sourceid": None,
                    "lastupdated": "2026-10-08",
                },
                [row(2023, None)] if page == 1 else [row(2024, 0)],
            ]
        else:
            raise AssertionError(path)
        raw = json.dumps(payload).encode()
        receipt = {
            "id": "test:"
            + hashlib.sha256((path + str(params)).encode()).hexdigest()[:24],
            "url": "https://api.worldbank.org/v2" + path,
            "http_status": 200,
            "retrieved_at": "2026-11-05T12:00:00Z",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "headers": {},
        }
        return payload, receipt, raw


class Response(io.BytesIO):
    status = 200
    headers: ClassVar = {"Content-Type": "application/json"}


class CountryContextTests(unittest.TestCase):
    def setUp(self):
        self.indicators = {CODE: parse_indicator_metadata(metadata(), CODE)}

    def test_null_zero_negative_and_unreturned_are_distinct(self):
        rows = [row(2020, None), row(2021, 0), row(2022, -2)]
        values, coverage = normalize_rows(rows, self.indicators, ["SYR"], 2020, 2023)
        self.assertEqual([item["value"] for item in values], [0, -2])
        self.assertEqual(coverage[0]["null_years"], [2020])
        self.assertEqual(coverage[0]["unreturned_years"], [2023])
        self.assertEqual(coverage[0]["observation_count"], 2)
        self.assertEqual(coverage[0]["zero_value_count"], 1)

    def test_status_forecasts_and_unknown_flags_are_withheld(self):
        values, coverage = normalize_rows(
            [row(2020, 10, "F"), row(2021, 20, "Z"), row(2022, 30)],
            self.indicators,
            ["SYR"],
            2020,
            2022,
        )
        self.assertEqual([item["value"] for item in values], [30])
        self.assertEqual(coverage[0]["forecast_years"], [2020])
        self.assertEqual(coverage[0]["unrecognized_status_years"], [2021])
        self.assertEqual(coverage[0]["null_years"], [])
        self.assertEqual(values[0]["obs_status"], "")

    def test_stable_ids_exact_values_original_units_and_no_decimal_scaling(self):
        rows = [row(2023, 12345.6789), row(2024, 0)]
        a, _ = normalize_rows(rows, self.indicators, ["SYR"], 2023, 2024)
        b, _ = normalize_rows(
            list(reversed(rows)), self.indicators, ["SYR"], 2023, 2024
        )
        self.assertEqual(a, b)
        self.assertEqual(a[0]["id"], "wdi:2:SYR:SP.POP.TOTL:2023")
        self.assertEqual(a[0]["value"], 12345.6789)
        self.assertEqual(a[0]["unit"], "persons")
        self.assertEqual(a[0]["unit_source_raw"], "")
        self.assertEqual(a[0]["decimal_source_raw"], 2)
        self.assertEqual(a[0]["attributes"]["countryiso3code"], "SYR")

    def test_invalid_dates_aggregates_duplicates_and_non_numeric_values_refuse(self):
        for changed in [
            {"date": "2024Q1"},
            {"date": "2025"},
            {"countryiso3code": "WLD"},
            {"value": True},
            {"value": float("nan")},
            {"value": "123"},
            {"value": 9_007_199_254_740_992},
        ]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                normalize_rows(
                    [{**row(2024, 1), **changed}], self.indicators, ["SYR"], 2024, 2024
                )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_rows(
                [row(2024, 1), row(2024, 2)], self.indicators, ["SYR"], 2024, 2024
            )

    def test_unlicensed_or_forecast_series_refuse_and_source_metadata_survives(self):
        for licence in ["", None, "CC BY-NC 4.0", "Proprietary"]:
            with (
                self.subTest(licence=licence),
                self.assertRaisesRegex(ValueError, "licence"),
            ):
                parse_indicator_metadata(metadata(licence), CODE)
        changed = metadata()
        changed["source"][0]["concept"][0]["variable"][0]["metatype"][0]["value"] = (
            "Projected population"
        )
        with self.assertRaisesRegex(ValueError, "forecast"):
            parse_indicator_metadata(changed, CODE)
        parsed = self.indicators[CODE]
        self.assertEqual(parsed["unit_source_raw"], "Unit")
        self.assertEqual(parsed["aggregation_method_source_raw"], "Sum")
        self.assertEqual(parsed["source_organizations"], "UN Population Division")

    def test_client_retries_only_bounded_transient_errors_and_hashes_raw_bytes(self):
        calls, sleeps = [], []
        raw = b'[{"page":1},[]]'

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "Slow down", {}, None)
            return Response(raw)

        client = WorldBankClient(opener=opener, sleeper=sleeps.append)
        payload, receipt, saved = client.get("/country/SYR", {"per_page": 1000})
        self.assertEqual(payload[0]["page"], 1)
        self.assertEqual(saved, raw)
        self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(sleeps, [0.5])
        self.assertEqual(len(calls), 2)
        self.assertTrue(receipt["url"].startswith("https://api.worldbank.org/v2/"))

    def test_client_refuses_http_200_error_documents_and_403_without_retry(self):
        client = WorldBankClient(
            opener=lambda *_args, **_kw: Response(b'[{"message":[{"id":"120"}]}]')
        )
        with self.assertRaisesRegex(ValueError, "API error"):
            client.get("/country/SYR")
        calls = []

        def denied(request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

        with self.assertRaises(HTTPError):
            WorldBankClient(
                opener=denied, sleeper=lambda _: self.fail("Must not retry403")
            ).get("/country/SYR")
        self.assertEqual(len(calls), 1)

    def test_collection_follows_pagination_and_refuses_interrupted_or_existing_output(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "snapshot"
            client = FakeClient()
            manifest = collect_snapshot(
                target,
                client=client,
                economies=["SYR"],
                indicator_codes=[CODE],
                start_year=2023,
                end_year=2024,
            )
            self.assertEqual(manifest["observation_count"], 1)
            self.assertEqual(manifest["returned_rows"], 2)
            self.assertEqual(manifest["null_value_count"], 1)
            self.assertEqual(manifest["zero_value_count"], 1)
            self.assertEqual(
                len(json.loads((target / "receipts.json").read_bytes())), 5
            )
            with self.assertRaisesRegex(ValueError, "Fresh"):
                collect_snapshot(target, client=client)
            failed = Path(temp) / "failed"
            with self.assertRaisesRegex(ValueError, "interrupted"):
                collect_snapshot(
                    failed,
                    client=FakeClient(True),
                    economies=["SYR"],
                    indicator_codes=[CODE],
                    start_year=2023,
                    end_year=2024,
                )
            self.assertFalse(failed.exists())
            self.assertEqual(list(Path(temp).glob(".wdi-*")), [])

    def test_future_or_unreviewed_scope_refuses_before_network(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as temp:
            for kwargs in [
                {"end_year": datetime.now(UTC).year},
                {"economies": ["WLD"]},
                {"indicator_codes": ["UNREVIEWED.SERIES"]},
            ]:
                with self.assertRaises(ValueError):
                    collect_snapshot(Path(temp) / "out", client=client, **kwargs)
        self.assertEqual(client.calls, [])

    def test_static_fragment_preserves_counts_hashes_iso2_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, output = Path(temp) / "repo", Path(temp) / "site"
            source = repo / "data/observations/world-bank"
            collect_snapshot(
                source,
                client=FakeClient(),
                economies=["SYR"],
                indicator_codes=[CODE],
                start_year=2023,
                end_year=2024,
            )
            fragment = build_static_bundle(repo, output)
            self.assertEqual(
                fragment["countries"], [{"code": "SY", "name": "Syrian Arab Republic"}]
            )
            shard = fragment["indicator_shards"][0]
            raw = (output / shard["path"].removeprefix("./")).read_bytes()
            self.assertEqual(shard["count"], 1)
            self.assertEqual(shard["sha256"], hashlib.sha256(raw).hexdigest())
            records = json.loads(raw)["records"]
            self.assertEqual(records[0]["value"], 0)
            self.assertEqual(records[0]["attributes"]["countryiso3code"], "SYR")
            self.assertIn("request_receipt_id", records[0]["attributes"])
            self.assertEqual(records[0]["attributes"]["display_unit"], "persons")
            self.assertEqual(records[0]["attributes"]["unit"], "")
            self.assertIn(
                "not a census", records[0]["attributes"]["interpretation_note"]
            )
            self.assertIn(
                "Blank", records[0]["attributes"]["source_status_interpretation"]
            )
            self.assertTrue(
                all(
                    not isinstance(value, (dict, list))
                    for value in records[0]["attributes"].values()
                )
            )
            self.assertNotIn("latitude", records[0])
            self.assertNotIn("longitude", records[0])
            self.assertTrue(
                (
                    output / fragment["datasets"][0]["metadata_path"].removeprefix("./")
                ).exists()
            )
            copy = Path(temp) / "copy"
            build_snapshot(copy, source_dir=source)
            self.assertEqual(
                (copy / "manifest.json").read_bytes(),
                (source / "manifest.json").read_bytes(),
            )
            (source / "countries/SYR.json").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_static_bundle(repo, Path(temp) / "tampered-site")


if __name__ == "__main__":
    unittest.main()
