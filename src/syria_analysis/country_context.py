"""Bounded, attributed World Bank country context; separate from event evidence.

Only the explicitly reviewed economies and annual WDI series are collected. Raw
JSON, request receipts, licences and missingness remain in the saved snapshot.
No forecasts, causal links, interpolation or regional aggregates are generated.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA = "tacitus-country-context/1"
API = "https://api.worldbank.org/v2"
SOURCE_ID = "2"
DATASET = "world-bank-wdi"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data/observations/world-bank"
ECONOMIES = ("SYR", "LBN", "JOR", "IRQ", "IRN", "TUR", "EGY", "ISR", "PSE", "YEM")
TERMS = "https://data.worldbank.org/summary-terms-of-use"

# Display labels qualify the source's sometimes generic/missing Unitofmeasure.
# They never rescale the numeric value or replace the original metadata.
_SERIES = [
    (
        "SP.POP.TOTL",
        "Population",
        "persons",
        "Midyear population estimate; not a census count.",
    ),
    ("SP.POP.GROW", "Population", "annual %", "Annual population growth rate."),
    (
        "SP.URB.TOTL.IN.ZS",
        "Population",
        "% of population",
        "Urban definitions differ across economies.",
    ),
    (
        "SP.POP.0014.TO.ZS",
        "Population",
        "% of population",
        "Population share ages 0–14.",
    ),
    (
        "SP.POP.DPND",
        "Population",
        "% of working-age population",
        "Age ratio; not an employment-dependency measure.",
    ),
    (
        "SM.POP.NETM",
        "Mobility",
        "persons",
        "Annual net migration estimate; not a refugee-flow count.",
    ),
    (
        "NY.GDP.MKTP.CD",
        "Economy",
        "current US$",
        "Nominal value; exchange-rate and price changes matter.",
    ),
    (
        "NY.GDP.MKTP.KD",
        "Economy",
        "constant 2015 US$",
        "National accounts estimate in constant prices.",
    ),
    (
        "NY.GDP.PCAP.KD",
        "Economy",
        "constant 2015 US$ per person",
        "GDP per capita is not household income.",
    ),
    (
        "NY.GDP.MKTP.KD.ZG",
        "Economy",
        "annual %",
        "Annual national accounts growth estimate.",
    ),
    (
        "FP.CPI.TOTL.ZG",
        "Economy",
        "annual %",
        "Consumer-price index growth; coverage follows source methods.",
    ),
    (
        "SL.UEM.TOTL.ZS",
        "Employment",
        "% of labor force",
        "Modeled ILO estimate; not a count of all non-working people.",
    ),
    (
        "SL.UEM.1524.ZS",
        "Employment",
        "% of labor force ages 15–24",
        "Modeled ILO estimate; denominator is the youth labor force.",
    ),
    (
        "SL.TLF.CACT.ZS",
        "Employment",
        "% of population ages 15+",
        "Modeled ILO labor-force participation estimate.",
    ),
    (
        "BX.TRF.PWKR.DT.GD.ZS",
        "Economy",
        "% of GDP",
        "Personal remittances received relative to GDP.",
    ),
    (
        "NE.TRD.GNFS.ZS",
        "Economy",
        "% of GDP",
        "Exports plus imports relative to GDP; can exceed 100%.",
    ),
    (
        "NV.AGR.TOTL.ZS",
        "Economy",
        "% of GDP",
        "Agriculture, forestry and fishing value added.",
    ),
    (
        "SP.DYN.LE00.IN",
        "Health",
        "years",
        "Period life-expectancy estimate; not an individual prediction.",
    ),
    (
        "SH.DYN.MORT",
        "Health",
        "per 1,000 live births",
        "Under-five mortality estimate; not a conflict-fatality count.",
    ),
    (
        "EG.ELC.ACCS.ZS",
        "Services",
        "% of population",
        "Electricity access does not measure reliability or hours of supply.",
    ),
    (
        "SH.H2O.BASW.ZS",
        "Services",
        "% of population",
        "At least basic service; not the safely-managed-water indicator.",
    ),
    (
        "SH.STA.BASS.ZS",
        "Services",
        "% of population",
        "At least basic sanitation service.",
    ),
    (
        "IT.NET.USER.ZS",
        "Services",
        "% of population",
        "Internet use does not measure connection speed or freedom of access.",
    ),
    (
        "SE.PRM.ENRR",
        "Education",
        "% gross",
        "Gross enrollment can exceed 100%; not an attendance rate.",
    ),
    (
        "SE.SEC.ENRR",
        "Education",
        "% gross",
        "Gross enrollment can exceed 100%; age and system definitions matter.",
    ),
    (
        "SH.XPD.CHEX.GD.ZS",
        "Health",
        "% of GDP",
        "Health expenditure share; not service quality or conflict expenditure.",
    ),
    (
        "BX.KLT.DINV.WD.GD.ZS",
        "Economy",
        "% of GDP",
        "Net inward foreign direct investment; can be negative and is not a reconstruction-spending measure.",
    ),
    (
        "NV.IND.TOTL.ZS",
        "Economy",
        "% of GDP",
        "Industry including construction value added; not a measure of wartime physical damage.",
    ),
    (
        "EN.POP.DNST",
        "Population",
        "people per square km of land",
        "National density; not local settlement density.",
    ),
    (
        "AG.LND.AGRI.ZS",
        "Environment",
        "% of land area",
        "Land use share; not agricultural production or food security.",
    ),
    (
        "ER.H2O.FWST.ZS",
        "Environment",
        "% ratio",
        "Water withdrawal relative to available resources; not a local incident.",
    ),
    (
        "TM.VAL.FOOD.ZS.UN",
        "Economy",
        "% of merchandise imports",
        "Import composition; not a food-insecurity prevalence measure.",
    ),
]
INDICATOR_SPECS = {
    code: {"topic": topic, "display_unit": unit, "interpretation_note": note}
    for code, topic, unit, note in _SERIES
}


def _json_bytes(value):
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class WorldBankClient:
    """HTTPS GET only; bounded body, timeout, retries and official origin."""

    def __init__(self, *, opener=urlopen, sleeper=time.sleep, timeout=25, attempts=3):
        if not 1 <= attempts <= 3 or not 0 < timeout <= 30:
            raise ValueError("Bounded timeout/attempts required")
        self.opener, self.sleeper = opener, sleeper
        self.timeout, self.attempts = timeout, attempts

    def get(self, path, params=None):
        if (
            not path.startswith(("/country/", "/sources/"))
            or ".." in path
            or "?" in path
        ):
            raise ValueError("Unsupported World Bank endpoint")
        query = {"format": "json", **(params or {})}
        url = API + path + "?" + urlencode(query, safe=";:")
        raw = None
        for attempt in range(self.attempts):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "TACITUS-Country-Context/1.0 (public annual data)",
                        "Accept": "application/json",
                    },
                )
                with self.opener(request, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise ValueError(f"Unexpected HTTP status {response.status}")
                    raw = response.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise ValueError("World Bank response exceeds 8 MiB")
                    headers = {
                        key.lower(): response.headers[key]
                        for key in ("Content-Type", "Date", "ETag", "Last-Modified")
                        if key in response.headers
                    }
                break
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                retryable = not isinstance(error, HTTPError) or error.code in (
                    429,
                    500,
                    502,
                    503,
                    504,
                )
                if not retryable or attempt + 1 == self.attempts:
                    raise
                self.sleeper(0.5 * (2**attempt))
        try:
            payload = json.loads(
                raw,
                parse_constant=lambda x: (_ for _ in ()).throw(
                    ValueError(f"Non-finite JSON value: {x}")
                ),
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("World Bank returned invalid JSON") from error
        if (
            isinstance(payload, dict)
            and "message" in payload
            or isinstance(payload, list)
            and len(payload) == 1
            and isinstance(payload[0], dict)
            and "message" in payload[0]
        ):
            raise ValueError(f"World Bank returned an API error document for {url}")
        receipt = {
            "id": "wb-request:" + _sha((url + "\n" + _sha(raw)).encode())[:24],
            "url": url,
            "http_status": 200,
            "retrieved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "sha256": _sha(raw),
            "bytes": len(raw),
            "headers": headers,
        }
        return payload, receipt, raw


def parse_indicator_metadata(payload, code):
    """Refuse absent/unlicensed/foreign/forecast metadata before publishing data."""
    if code not in INDICATOR_SPECS or not isinstance(payload, dict):
        raise ValueError("Indicator is outside the reviewed series allowlist")
    matches = [
        variable
        for source in payload.get("source", [])
        if str(source.get("id")) == SOURCE_ID
        for concept in source.get("concept", [])
        if concept.get("id") == "Series"
        for variable in concept.get("variable", [])
        if variable.get("id") == code
    ]
    if len(matches) != 1:
        raise ValueError("Expected exact, unique WDI series metadata")
    fields = {}
    for item in matches[0].get("metatype", []):
        if item["id"] in fields:
            raise ValueError("Duplicate metadata field")
        fields[item["id"]] = item.get("value")
    if fields.get("License_Type") not in ("CC BY-4.0", "CC BY 4.0"):
        raise ValueError(f"Series lacks an approved redistribution licence: {code}")
    licence_url = fields.get("License_URL", "")
    if licence_url not in (
        "https://datacatalog.worldbank.org/public-licenses#cc-by",
        "https://creativecommons.org/licenses/by/4.0/",
    ):
        raise ValueError("Unrecognized per-series licence URL")
    if (
        fields.get("Periodicity") != "Annual"
        or not fields.get("IndicatorName")
        or not fields.get("Longdefinition")
    ):
        raise ValueError("Annual definition metadata required")
    if re.search(
        r"\b(forecast|forecasted|projected|projection)\b",
        fields["IndicatorName"],
        re.IGNORECASE,
    ):
        raise ValueError("Forward-forecast series excluded")
    return {
        "id": code,
        "source_id": SOURCE_ID,
        "dataset": DATASET,
        "name": fields["IndicatorName"],
        **INDICATOR_SPECS[code],
        "unit_source_raw": fields.get("Unitofmeasure"),
        "unit_display_basis": "Reviewed indicator name and definition; original unit metadata retained; no scaling applied.",
        "periodicity": fields["Periodicity"],
        "reference_period": fields.get("Referenceperiod"),
        "aggregation_method_source_raw": fields.get("Aggregationmethod"),
        "definition": fields["Longdefinition"],
        "source_organizations": fields.get("Source"),
        "limitations": fields.get("Limitationsandexceptions"),
        "methodology": fields.get("Statisticalconceptandmethodology"),
        "metadata_fields": fields,
        "licence": {
            "id": "CC-BY-4.0",
            "source_label": fields["License_Type"],
            "url": licence_url,
            "terms_url": TERMS,
        },
        "source_url": f"https://data.worldbank.org/indicator/{code}",
        "metadata_url": f"{API}/sources/2/series/{code}/metadata?format=json",
        "cell_estimate_or_projection_status": "Not inferred. Preserve obs_status; consult source methodology. Blank status is unknown.",
    }


def normalize_rows(rows, indicators, countries, start_year, end_year):
    """Numeric cells only; null and unreturned years stay in separate coverage."""
    expected = {(country, code): {} for country in countries for code in indicators}
    withheld = {
        (country, code): {"forecast_years": [], "unrecognized_status_years": []}
        for country in countries
        for code in indicators
    }
    observations = []
    for row in rows:
        country, code, period = (
            row.get("countryiso3code"),
            row.get("indicator", {}).get("id"),
            row.get("date"),
        )
        if (
            (country, code) not in expected
            or not isinstance(period, str)
            or not re.fullmatch(r"\d{4}", period)
        ):
            raise ValueError("Unexpected economy, indicator or non-annual period")
        year = int(period)
        if not start_year <= year <= end_year or year in expected[country, code]:
            raise ValueError("Out-of-range or duplicate country/indicator/year")
        value = row.get("value")
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or abs(value) > 9_007_199_254_740_991
        ):
            raise ValueError("Observation must be a finite number or null")
        expected[country, code][year] = value
        if value is None:
            continue
        status = row.get("obs_status")
        if status not in (None, ""):
            # The World Bank documents F as forecast. Other nonblank statuses
            # are withheld pending a reviewed meaning rather than guessed.
            kind = (
                "forecast_years"
                if str(status).strip().upper() == "F"
                else "unrecognized_status_years"
            )
            withheld[country, code][kind].append(year)
            continue
        observations.append(
            {
                "id": f"wdi:2:{country}:{code}:{year}",
                "dataset": DATASET,
                "economy": country,
                "indicator": code,
                "year": year,
                "period": period,
                "value": value,
                "unit": indicators[code]["display_unit"],
                "unit_source_raw": row.get("unit"),
                "decimal_source_raw": row.get("decimal"),
                "obs_status": row.get("obs_status"),
                "footnote": row.get("footnote"),
                "attributes": {
                    "indicator_id": code,
                    "indicator_name": row.get("indicator", {}).get("value"),
                    "country_id": row.get("country", {}).get("id"),
                    "country_name": row.get("country", {}).get("value"),
                    "countryiso3code": country,
                    "date": period,
                    "value": value,
                    "unit": row.get("unit"),
                    "decimal": row.get("decimal"),
                    "obs_status": row.get("obs_status"),
                    "footnote": row.get("footnote"),
                },
            }
        )
    observations.sort(
        key=lambda item: (item["economy"], item["indicator"], item["year"])
    )
    coverage = []
    for (country, code), values in sorted(expected.items()):
        excluded = {
            year for years in withheld[country, code].values() for year in years
        }
        numeric = sorted(
            year
            for year, value in values.items()
            if value is not None and year not in excluded
        )
        coverage.append(
            {
                "economy": country,
                "indicator": code,
                "requested_period": [start_year, end_year],
                "returned_rows": len(values),
                "observation_count": len(numeric),
                "null_years": sorted(
                    year for year, value in values.items() if value is None
                ),
                "forecast_years": sorted(withheld[country, code]["forecast_years"]),
                "unrecognized_status_years": sorted(
                    withheld[country, code]["unrecognized_status_years"]
                ),
                "unreturned_years": [
                    year
                    for year in range(start_year, end_year + 1)
                    if year not in values
                ],
                "first_value_year": numeric[0] if numeric else None,
                "last_value_year": numeric[-1] if numeric else None,
                "zero_value_count": sum(
                    value == 0
                    for year, value in values.items()
                    if value is not None and year not in excluded
                ),
            }
        )
    return observations, coverage


def collect_snapshot(
    output_dir,
    *,
    client=None,
    start_year=1960,
    end_year=2025,
    economies=ECONOMIES,
    indicator_codes=None,
):
    """Collect into a fresh directory atomically; never overwrite a snapshot."""
    output_dir = Path(output_dir)
    codes = tuple(indicator_codes or INDICATOR_SPECS)
    economies = tuple(economies)
    if (
        not economies
        or len(set(economies)) != len(economies)
        or not set(economies) <= set(ECONOMIES)
    ):
        raise ValueError("Explicit reviewed economies only; aggregates are excluded")
    if (
        not codes
        or len(set(codes)) != len(codes)
        or not set(codes) <= set(INDICATOR_SPECS)
    ):
        raise ValueError("Explicit reviewed indicators only")
    if not 1960 <= start_year <= end_year < datetime.now(UTC).year:
        raise ValueError("Complete historical annual periods only")
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("Fresh output directory required")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".wdi-", dir=output_dir.parent))
    client = client or WorldBankClient()
    receipts = []

    def save_response(result, filename):
        payload, receipt, raw = result
        path = staging / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        receipts.append({**receipt, "raw_path": filename})
        return payload

    try:
        source = save_response(client.get("/sources/2"), "raw/source.json")
        if (
            not isinstance(source, list)
            or len(source) != 2
            or len(source[1]) != 1
            or str(source[1][0].get("id")) != SOURCE_ID
        ):
            raise ValueError("Expected WDI source metadata")
        source_updated = source[1][0].get("lastupdated")
        if not isinstance(source_updated, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", source_updated
        ):
            raise ValueError("Source update date required")
        country_data = save_response(
            client.get("/country/" + ";".join(economies), {"per_page": 1000}),
            "raw/countries.json",
        )
        countries = (
            country_data[1]
            if isinstance(country_data, list) and len(country_data) == 2
            else []
        )
        if len(countries) != len(economies) or {
            item.get("id") for item in countries
        } != set(economies):
            raise ValueError("Missing or unexpected economy metadata")
        if any(
            item.get("region", {}).get("value") == "Aggregates"
            or item.get("region", {}).get("id") == "NA"
            for item in countries
        ):
            raise ValueError("Regional/income aggregates are excluded")
        # The selected economy response contains capital coordinates. They are
        # retained only in its raw receipt; no country indicator becomes a point.
        countries = sorted(
            (
                {"id": item["id"], "iso2": item["iso2Code"], "name": item["name"]}
                for item in countries
            ),
            key=lambda item: item["id"],
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = pool.map(
                lambda code: client.get(f"/sources/2/series/{code}/metadata"), codes
            )
            indicators = {}
            for code, response in zip(codes, responses):
                payload = save_response(response, f"raw/metadata/{code}.json")
                indicators[code] = parse_indicator_metadata(payload, code)
        rows = []
        for batch in range(0, len(codes), 4):
            batch_codes = codes[batch : batch + 4]
            page = 1
            count = 0
            while True:
                path = (
                    "/country/"
                    + ";".join(economies)
                    + "/indicator/"
                    + ";".join(batch_codes)
                )
                params = {
                    "source": SOURCE_ID,
                    "date": f"{start_year}:{end_year}",
                    "footnote": "y",
                    "per_page": 5000,
                    "page": page,
                }
                data = save_response(
                    client.get(path, params),
                    f"raw/data/batch-{batch // 4:02d}-page-{page}.json",
                )
                if (
                    not isinstance(data, list)
                    or len(data) != 2
                    or not isinstance(data[0], dict)
                    or not isinstance(data[1], list)
                ):
                    raise ValueError("Expected paginated World Bank data response")
                header, page_rows = data
                # The live API returns sourceid:null for a multi-indicator
                # request even with source=2. The exact query plus each series'
                # source-2 metadata establish the source; retain the raw header.
                if header.get("sourceid") not in (None, SOURCE_ID, 2):
                    raise ValueError("Unexpected response source ID")
                if header.get("lastupdated") != source_updated:
                    raise ValueError(
                        "Source changed during collection; retry a new snapshot"
                    )
                pages, total = int(header["pages"]), int(header["total"])
                if (
                    not 1 <= pages <= 100
                    or int(header["page"]) != page
                    or total > 50000
                ):
                    raise ValueError("Invalid or excessive pagination")
                if page == 1:
                    expected_total, expected_pages = total, pages
                if (total, pages) != (expected_total, expected_pages):
                    raise ValueError("Pagination changed during collection")
                rows.extend(page_rows)
                count += len(page_rows)
                if page == pages:
                    if count != total:
                        raise ValueError("Pagination incomplete")
                    break
                page += 1
        observations, coverage = normalize_rows(
            rows, indicators, economies, start_year, end_year
        )
        if not observations:
            raise ValueError("No non-null numeric observations collected")
        indicators = [indicators[code] for code in sorted(indicators)]
        files = {
            "countries.json": countries,
            "indicators.json": indicators,
            "coverage.json": coverage,
            "receipts.json": sorted(receipts, key=lambda item: item["raw_path"]),
        }
        for filename, value in files.items():
            (staging / filename).write_bytes(_json_bytes(value))
        (staging / "observations.jsonl").write_bytes(
            b"".join(_json_bytes(item) for item in observations)
        )
        (staging / "countries").mkdir()
        for country in countries:
            shard = {
                "schema": SCHEMA,
                "economy": country,
                "observations": [
                    item for item in observations if item["economy"] == country["id"]
                ],
            }
            (staging / "countries" / f"{country['id']}.json").write_bytes(
                _json_bytes(shard)
            )
        manifest = {
            "schema": SCHEMA,
            "dataset": DATASET,
            "source_id": SOURCE_ID,
            "source_name": "World Development Indicators",
            "source_last_updated": source_updated,
            "retrieved_at": max(item["retrieved_at"] for item in receipts),
            "requested_period": [start_year, end_year],
            "economies": [item["id"] for item in countries],
            "indicator_count": len(indicators),
            "observation_count": len(observations),
            "returned_rows": len(rows),
            "null_value_count": sum(len(item["null_years"]) for item in coverage),
            "withheld_forecast_count": sum(
                len(item["forecast_years"]) for item in coverage
            ),
            "withheld_unrecognized_status_count": sum(
                len(item["unrecognized_status_years"]) for item in coverage
            ),
            "unreturned_cell_count": sum(
                len(item["unreturned_years"]) for item in coverage
            ),
            "zero_value_count": sum(item["value"] == 0 for item in observations),
            "by_economy": {
                country["id"]: sum(
                    item["economy"] == country["id"] for item in observations
                )
                for country in countries
            },
            "licence": {
                "id": "CC-BY-4.0",
                "terms_url": TERMS,
                "per_series_metadata_checked": True,
            },
            "attribution": "The World Bank: World Development Indicators: original data providers named in each indicator’s metadata. Retrieved "
            + max(item["retrieved_at"] for item in receipts)[:10]
            + ".",
            "semantics": {
                "frequency": "annual",
                "geographic_scope": "economy; never geocoded as an event",
                "cell_estimate_status": "F forecasts and unrecognized nonblank flags withheld. Blank is unknown, not proof of direct measurement; consult series methodology.",
                "null_policy": "Null rows are excluded from observation counts and retained in raw responses and coverage.null_years. Unreturned years remain separate.",
                "transformation": "No rescaling, interpolation, carry-forward, gap filling, region aggregation or causal link generation.",
                "period_policy": "Calendar labels from the annual API; measurement timing, estimates and fiscal comparability follow indicator metadata.",
                "conflict_relation": "Country/year alignment is contextual only; it is not evidence that a conflict event caused a change.",
            },
            "automatic_refresh": False,
        }
        manifest["files"] = {
            str(path.relative_to(staging)): {
                "sha256": _sha(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "manifest.json").write_bytes(_json_bytes(manifest))
        os.replace(staging, output_dir)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _verified_snapshot(source_dir):
    source_dir = Path(source_dir).resolve()
    manifest = json.loads((source_dir / "manifest.json").read_bytes())
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported country-context snapshot")
    files = manifest.get("files", {})
    for name, receipt in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe snapshot path")
        path = source_dir / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or source_dir not in path.resolve().parents
        ):
            raise ValueError("Invalid snapshot file")
        raw = path.read_bytes()
        if len(raw) != receipt["bytes"] or _sha(raw) != receipt["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {name}")
    for metadata in json.loads((source_dir / "indicators.json").read_bytes()):
        raw = json.loads(
            (source_dir / "raw/metadata" / (metadata["id"] + ".json")).read_bytes()
        )
        reviewed = parse_indicator_metadata(raw, metadata["id"])
        if metadata != reviewed:
            raise ValueError("Unsupported indicator licence")
    return manifest


def build_snapshot(output_dir, *, source_dir=DEFAULT_DATA_DIR):
    """Copy a verified snapshot to a separate build directory; no network."""
    source_dir, output_dir = Path(source_dir).resolve(), Path(output_dir).resolve()
    if (
        source_dir == output_dir
        or source_dir in output_dir.parents
        or output_dir in source_dir.parents
    ):
        raise ValueError("Build destination must be separate from source snapshot")
    manifest = _verified_snapshot(source_dir)
    files = manifest["files"]
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in [*files, "manifest.json"]:
        target = output_dir / name
        if target.is_symlink() or output_dir not in target.resolve().parents:
            raise ValueError("Unsafe build destination")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_dir / name, target)
    return manifest


def build_static_bundle(repository, output):
    """Emit the shared observation-atlas manifest fragment and ISO2 shards.

    All paths in the returned fragment are relative to ``output``. The committed
    snapshot is verified, never refreshed implicitly. Country context has no
    coordinates or inferred relationships to conflict-event records.
    """
    source = Path(repository).resolve() / "data/observations/world-bank"
    output = Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Static output must be separate from committed data")
    manifest = _verified_snapshot(source)
    countries = json.loads((source / "countries.json").read_bytes())
    indicators = {
        item["id"]: item
        for item in json.loads((source / "indicators.json").read_bytes())
    }
    receipts = json.loads((source / "receipts.json").read_bytes())
    lookup = {}
    for receipt in receipts:
        if receipt["raw_path"].startswith("raw/data/"):
            for row in json.loads((source / receipt["raw_path"]).read_bytes())[1]:
                lookup[row["countryiso3code"], row["indicator"]["id"], row["date"]] = (
                    receipt["id"]
                )
    target = output / "data/indicators"
    if target.is_symlink() or output not in target.resolve().parents:
        raise ValueError("Unsafe static output")
    target.mkdir(parents=True, exist_ok=True)

    def check_attributes(attributes):
        if len(attributes) > 128:
            raise ValueError("Too many observation attributes")
        for key, value in attributes.items():
            if not isinstance(key, str) or not key or len(key) > 120:
                raise ValueError("Invalid attribute key")
            if isinstance(value, str):
                if len(value) > 20000:
                    raise ValueError("Attribute text exceeds export bound")
            elif value is None or isinstance(value, bool):
                continue
            elif isinstance(value, (int, float)):
                if not math.isfinite(value) or abs(value) > 9_007_199_254_740_991:
                    raise ValueError("Attribute number exceeds JavaScript-safe bounds")
            else:
                raise ValueError("Observation attributes must remain flat primitives")

    shards, total = [], 0
    for country in countries:
        iso2 = country["iso2"]
        if not re.fullmatch(r"[A-Z]{2}", iso2):
            raise ValueError("Explicit ISO2 economy code required")
        rows = json.loads(
            (source / "countries" / (country["id"] + ".json")).read_bytes()
        )["observations"]
        records = []
        for row in rows:
            metadata = indicators[row["indicator"]]
            attributes = {
                **row["attributes"],
                "source_id_requested": SOURCE_ID,
                "source_last_updated": manifest["source_last_updated"],
                "request_receipt_id": lookup[
                    country["id"], row["indicator"], row["period"]
                ],
                "display_unit": row["unit"],
                "display_unit_basis": metadata["unit_display_basis"],
                "interpretation_note": metadata["interpretation_note"],
                "source_status_interpretation": "Blank provider status. Direct measurement versus estimate/projection is not supplied at cell level; consult methodology.",
                "source_indicator_metadata": metadata["metadata_url"],
            }
            check_attributes(attributes)
            locator = f"{API}/country/{country['id']}/indicator/{row['indicator']}?source=2&date={row['year']}&format=json&footnote=y"
            records.append(
                {
                    "id": row["id"],
                    "dataset_id": DATASET,
                    "country_code": iso2,
                    "indicator_code": row["indicator"],
                    "indicator_name": metadata["name"],
                    "year": row["year"],
                    "value": row["value"],
                    "unit": row["unit"],
                    "status": "Source status unspecified",
                    "source_locator": locator,
                    "attributes": attributes,
                }
            )
        chunks, chunk = [], []
        size = len(_json_bytes({"records": []}))
        for record in records:
            addition = len(_json_bytes(record)) - 1 + bool(chunk)
            if size + addition > 1_500_000:
                if not chunk:
                    raise ValueError("Single observation exceeds shard bound")
                chunks.append(chunk)
                chunk = []
                size = len(_json_bytes({"records": []}))
                addition -= 1
            chunk.append(record)
            size += addition
        if chunk or not records:
            chunks.append(chunk)
        # Only these generated World Bank country filenames are owned here.
        for old in [target / f"{iso2}.json", *target.glob(f"{iso2}-[0-9][0-9].json")]:
            if old.is_symlink():
                raise ValueError("Unsafe existing country shard")
            if old.is_file():
                old.unlink()
        for number, chunk in enumerate(chunks, 1):
            raw = _json_bytes({"records": chunk})
            if len(raw) > 1_572_864:
                raise ValueError("Country indicator shard exceeds 1.5 MiB")
            filename = f"data/indicators/{iso2}-{number:02d}.json"
            path = output / filename
            if path.is_symlink() or output not in path.resolve().parents:
                raise ValueError("Unsafe country shard destination")
            path.write_bytes(raw)
            shards.append(
                {
                    "path": "./" + filename,
                    "dataset_id": DATASET,
                    "country_code": iso2,
                    "count": len(chunk),
                    "sha256": _sha(raw),
                }
            )
        total += len(records)
    if total != manifest["observation_count"]:
        raise ValueError("Country partitions disagree with snapshot count")
    # Metadata/receipts are separate lazy assets. Raw responses retain nulls and
    # complete original series methodology, not a full-world catalogue dump.
    for filename in [
        "manifest.json",
        "countries.json",
        "indicators.json",
        "coverage.json",
        "receipts.json",
        *[name for name in manifest["files"] if name.startswith("raw/")],
    ]:
        path = target / "metadata" / filename
        if path.is_symlink() or output not in path.resolve().parents:
            raise ValueError("Unsafe provenance destination")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / filename, path)
    limits = [
        "Annual economy-level context; not local conditions or conflict-event evidence.",
        "Nulls and unreturned periods are separate coverage gaps, never zero, interpolation or carried-forward values.",
        "Values can be model estimates. Blank provider status is unknown; explicitly flagged forecasts and unrecognized flags are withheld.",
        "Each series has its own units, denominator, coverage and source methodology; no regional totals or causal links are computed.",
        "Same country/year alignment with conflict events is descriptive and does not identify a causal relationship.",
    ]
    dataset = {
        "id": DATASET,
        "kind": "country_indicator",
        "title": "World Development Indicators · selected Middle East economies",
        "version": manifest["source_last_updated"],
        "publisher": "World Bank and the original providers named in indicator metadata",
        "url": "https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators",
        "license": "CC-BY-4.0; World Bank dataset terms also apply",
        "sha256": _sha((source / "manifest.json").read_bytes()),
        "coverage": {
            "years": manifest["requested_period"],
            "indicator_count": len(indicators),
            "observation_count": total,
            "null_value_count": manifest["null_value_count"],
            "economy_count": len(countries),
        },
        "limitations": limits,
        "attribution": manifest["attribution"],
        "license_url": TERMS,
        "metadata_path": "./data/indicators/metadata/indicators.json",
        "coverage_path": "./data/indicators/metadata/coverage.json",
        "receipts_path": "./data/indicators/metadata/receipts.json",
        "snapshot_path": "./data/indicators/metadata/manifest.json",
        "raw_base_path": "./data/indicators/metadata/",
        "source_metadata_sha256": manifest["files"]["raw/source.json"]["sha256"],
    }
    return {
        "datasets": [dataset],
        "countries": [
            {"code": item["iso2"], "name": item["name"]} for item in countries
        ],
        "indicator_shards": shards,
        "limitations": limits,
    }
