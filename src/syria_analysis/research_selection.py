"""Bounded, source-attributed research selections; never native TACITUS capsules."""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

FORMAT = "policy-research-selection/1"
MAX_BYTES = 1024 * 1024
MAX_RECORDS = 200
DATASET_FIELDS = ("id", "title", "version", "publisher", "url", "license", "sha256")
RECORD_FIELDS = (
    "id",
    "kind",
    "dataset_id",
    "label",
    "country_code",
    "date_start",
    "date_end",
    "source_locator",
    "attributes",
)
NOTE_FIELDS = ("assessment", "alternatives", "gaps")
ENVELOPE_FIELDS = (
    "format",
    "created_at",
    "question",
    "datasets",
    "filters",
    "counts",
    "records",
    "notes",
    "limitations",
)
UNSAFE_KEYS = {"__proto__", "prototype", "constructor"}


def _text(value, maximum, *, blank=False):
    return (
        isinstance(value, str)
        and len(value) <= maximum
        and (blank or bool(value.strip()))
    )


def _day(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _integer(value):
    return type(value) is int and 0 <= value <= 2**53 - 1


def _primitive(value):
    if value is None or isinstance(value, (str, bool)):
        return True
    if type(value) is int:
        return abs(value) <= 2**53 - 1
    return type(value) is float and math.isfinite(value) and abs(value) <= 2**53 - 1


def _filters_safe(value):
    """Bounded JSON, not executable expressions or arbitrary recursive input."""
    queue = [(value, 0)]
    nodes = 0
    while queue:
        current, depth = queue.pop()
        nodes += 1
        if nodes > 500 or depth > 5:
            return False
        if isinstance(current, dict):
            if len(current) > 100:
                return False
            if any(not _text(k, 120) or k in UNSAFE_KEYS for k in current):
                return False
            queue.extend((v, depth + 1) for v in current.values())
        elif isinstance(current, list):
            if len(current) > 200:
                return False
            queue.extend((v, depth + 1) for v in current)
        elif not _primitive(current) or (
            isinstance(current, str) and len(current) > 2000
        ):
            return False
    return True


def validate_selection(pack):
    """Return readable errors without normalizing, repairing or trusting the input."""
    errors = []
    if not isinstance(pack, dict) or set(pack) != set(ENVELOPE_FIELDS):
        return ["Selection must have the exact policy-research-selection/1 envelope"]
    if pack["format"] != FORMAT:
        errors.append("Unsupported research-selection format")
    try:
        stamp = pack["created_at"]
        if not isinstance(stamp, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
            stamp,
        ):
            raise ValueError()
        parsed = datetime.fromisoformat(stamp)
        if parsed.utcoffset() is None:
            raise ValueError()
        if stamp[-1] != "Z":
            hours, minutes = map(int, stamp[-5:].split(":"))
            if hours > 23 or minutes > 59:
                raise ValueError()
    except (ValueError, TypeError):
        errors.append("created_at must be an ISO timestamp with a timezone")
    if not _text(pack["question"], 2000, blank=True):
        errors.append("Question must be text of at most 2000 characters")
    if not isinstance(pack["filters"], dict) or not _filters_safe(pack["filters"]):
        errors.append("Filters exceed the bounded JSON contract")

    datasets = pack["datasets"]
    ids = set()
    if not isinstance(datasets, list) or not 1 <= len(datasets) <= 2:
        errors.append("Provide one or two source datasets")
        datasets = []
    for item in datasets:
        if not isinstance(item, dict) or set(item) != set(DATASET_FIELDS):
            errors.append("Each dataset must contain exactly seven metadata fields")
            continue
        if any(
            not _text(item[k], 4096 if k == "url" else 2000) for k in DATASET_FIELDS
        ):
            errors.append("Dataset metadata must be nonempty bounded text")
            continue
        if len(item["id"]) > 200 or item["id"] in ids:
            errors.append(
                "Dataset identifiers must be unique and at most 200 characters"
            )
        ids.add(item["id"])
        try:
            url = urlsplit(item["url"])
            # Accessing .port validates a numeric, in-range port; .hostname alone does not.
            _ = url.port
            safe_url = (
                not re.search(r"[\s\\\x00-\x1f\x7f]", item["url"])
                and url.scheme == "https"
                and url.hostname
                and not (url.username or url.password)
            )
        except ValueError:
            safe_url = False
        if not safe_url:
            errors.append("Dataset URL must be HTTPS without embedded credentials")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", item["sha256"]):
            errors.append("Dataset sha256 must contain 64 hexadecimal characters")

    records = pack["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        errors.append("Selection may contain at most 200 records")
        records = []
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != set(RECORD_FIELDS):
            errors.append("Research record has unsupported or missing fields")
            continue
        if not _text(row["id"], 200) or row["id"] in seen:
            errors.append("Record identifiers must be unique bounded text")
        seen.add(row["id"]) if isinstance(row["id"], str) else None
        if row["kind"] not in ("conflict_event", "country_indicator"):
            errors.append("Record kind is unsupported")
        if not isinstance(row["dataset_id"], str) or row["dataset_id"] not in ids:
            errors.append("Every record must resolve to its supplied dataset metadata")
        if not _text(row["label"], 500) or not _text(row["source_locator"], 2000):
            errors.append("Record label or source locator is missing or too long")
        if not isinstance(row["country_code"], str) or not re.fullmatch(
            "[A-Z]{2}", row["country_code"]
        ):
            errors.append("Country code must be uppercase ISO2")
        if not _day(row["date_start"]) or not _day(row["date_end"]):
            errors.append("Record dates must be real ISO calendar days")
        elif row["date_start"] > row["date_end"]:
            errors.append("Record date interval is reversed")
        attrs = row["attributes"]
        if not isinstance(attrs, dict) or len(attrs) > 128:
            errors.append(
                "Record attributes must be a flat object with at most 128 fields"
            )
        elif any(
            not _text(k, 120)
            or k in UNSAFE_KEYS
            or not _primitive(v)
            or (isinstance(v, str) and len(v) > 20000)
            for k, v in attrs.items()
        ):
            errors.append(
                "Record attributes must retain bounded finite primitive values"
            )

    counts = pack["counts"]
    if not isinstance(counts, dict) or set(counts) != {
        "matched",
        "exported",
        "truncated",
        "limit",
    }:
        errors.append("Selection counts are missing or unsupported")
    elif (
        not all(_integer(counts[k]) for k in ("matched", "exported", "limit"))
        or type(counts["truncated"]) is not bool
        or not 1 <= counts["limit"] <= MAX_RECORDS
        or counts["exported"] != len(records)
        or counts["exported"] > counts["limit"]
        or counts["matched"] < counts["exported"]
        or counts["truncated"] != (counts["matched"] > counts["exported"])
    ):
        errors.append("Counts must describe the exact exported prefix and omissions")
    notes = pack["notes"]
    if (
        not isinstance(notes, dict)
        or set(notes) != set(NOTE_FIELDS)
        or any(not _text(v, 10000, blank=True) for v in notes.values())
    ):
        errors.append("Analyst notes must remain three bounded text fields")
    limitations = pack["limitations"]
    if (
        not isinstance(limitations, list)
        or len(limitations) > 30
        or any(not _text(v, 4000) for v in limitations)
    ):
        errors.append("Provide at most 30 bounded limitation statements")
    return errors


def selection_bytes(pack):
    return (
        json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_selection(payload):
    """Validate bytes while allowing the caller to preserve them exactly for re-export."""
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise ValueError("Research selections must be at most 1 MiB")
    try:
        pack = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Research selection is not valid UTF-8 JSON") from None
    errors = validate_selection(pack)
    if errors:
        raise ValueError("; ".join(errors))
    return pack


def make_selection(
    records,
    datasets,
    *,
    question="",
    filters=None,
    notes=None,
    limit=MAX_RECORDS,
    matched=None,
    limitations=None,
    created_at=None,
):
    """Export a visible, deterministic prefix; never silently erase the omitted count."""
    if type(limit) is not int or not 1 <= limit <= MAX_RECORDS:
        raise ValueError("Selection limit must be between one and 200")
    matched = len(records) if matched is None else matched
    if not _integer(matched) or matched < len(records):
        raise ValueError("Matched count cannot be smaller than the supplied selection")
    pack = {
        "format": FORMAT,
        "created_at": created_at
        or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "question": question,
        "datasets": [{key: item[key] for key in DATASET_FIELDS} for item in datasets],
        "filters": deepcopy(filters or {}),
        "counts": {
            "matched": matched,
            "exported": 0,
            "truncated": matched > 0,
            "limit": limit,
        },
        "records": [],
        "notes": {key: (notes or {}).get(key, "") for key in NOTE_FIELDS},
        "limitations": list(limitations or []),
    }
    for record in records[:limit]:
        pack["records"].append({key: deepcopy(record[key]) for key in RECORD_FIELDS})
        pack["counts"]["exported"] = len(pack["records"])
        pack["counts"]["truncated"] = matched > len(pack["records"])
        if len(selection_bytes(pack)) > MAX_BYTES:
            pack["records"].pop()
            break
    pack["counts"]["exported"] = len(pack["records"])
    pack["counts"]["truncated"] = matched > len(pack["records"])
    errors = validate_selection(pack)
    if errors or len(selection_bytes(pack)) > MAX_BYTES:
        raise ValueError(
            "; ".join(errors) or "Metadata exceeds the 1 MiB selection limit"
        )
    return pack
