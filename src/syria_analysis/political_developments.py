"""Bounded, source-qualified political acts and a transparent media worked study.

These records never derive political acts or outcomes from organized-violence
observations. Building and validating this small public pack requires no network,
model, database, credential or third-party dependency.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

FORMAT = "political-evidence-study/1"
SELECTION_FORMAT = "political-development-selection/1"
MAX_BYTES = 512 * 1024
MAX_QUESTION = 2000
KINDS = {
    "adoption",
    "announcement",
    "invitation",
    "meeting",
    "appointment",
    "agreement",
    "announced_programme",
    "reported_implementation",
}
REVIEW = "automated_source_check_pending_human_review"
HEX = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,100}\Z")


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, maximum=4000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def bounded(value):
    """Reject deeply nested, oversized or non-portable JSON before semantic work."""
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(
            depth <= 14 and count <= 30000, "Evidence exceeds JSON depth/value bounds"
        )
        if isinstance(item, dict):
            require(len(item) <= 200, "Too many object properties")
            for key, child in item.items():
                require(
                    text(key, 120)
                    and key
                    not in {
                        "__proto__",
                        "constructor",
                        "prototype",
                        "bias_score",
                        "credibility_score",
                        "trust_score",
                    },
                    "Unsafe JSON key or unsupported publisher score",
                )
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            require(len(item) <= 500, "Too many array members")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            require(len(item) <= 10000, "Oversized evidence text")
        else:
            require(
                item is None
                or type(item) is bool
                or (type(item) is int and abs(item) <= 2**53 - 1),
                "Evidence requires portable JSON values",
            )
    try:
        payload = canonical(value)
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ValueError("Evidence cannot be encoded as UTF-8 JSON") from exc
    require(len(payload) <= MAX_BYTES, "Evidence exceeds 512 KiB")
    return payload


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON key")
        value[key] = item
    return value


def read_json(path):
    with Path(path).open("rb") as handle:
        payload = handle.read(MAX_BYTES + 1)
    require(len(payload) <= MAX_BYTES, "Input exceeds 512 KiB")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 JSON") from exc
    bounded(value)
    return value


def exact_date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def safe_url(value):
    if not text(value, 2000):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return False
        if host.lower() in {
            "localhost",
            "localhost.localdomain",
        } or host.lower().endswith(".local"):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host and not any(char.isspace() for char in host)
    except (ValueError, TypeError):
        return False


def validate_review(review):
    require(
        isinstance(review, dict)
        and review.get("state") == REVIEW
        and review.get("human_review_recorded") is False,
        "Retain pending human review; do not promote automated checks",
    )


def source_index(sources):
    require(
        isinstance(sources, list) and 1 <= len(sources) <= 30,
        "Provide one to 30 attributed sources",
    )
    result, excerpts = {}, {}
    for source in sources:
        require(isinstance(source, dict), "Source must be an object")
        require(
            set(source)
            == {
                "id",
                "publisher",
                "title",
                "url",
                "source_kind",
                "byline",
                "published_on",
                "published_at",
                "modified_at",
                "publication_precision",
                "retrieved_on",
                "response_saved_at",
                "checked_at",
                "capture",
                "excerpts",
                "review_state",
                "human_review_recorded",
                "rights_note",
            },
            "Source must contain only declared metadata and selected excerpts",
        )
        sid = source.get("id")
        require(
            isinstance(sid, str) and ID.fullmatch(sid) and sid not in result,
            "Source IDs must be unique",
        )
        require(
            safe_url(source.get("url")),
            "Source URL must be public HTTPS without embedded credentials",
        )
        require(
            text(source.get("title")) and text(source.get("publisher"), 300),
            "Source requires title and publisher",
        )
        require(
            source.get("source_kind")
            in {
                "primary_instrument",
                "institutional_reporting",
                "primary_announcement",
                "news_report",
                "analysis",
            },
            "Unknown source type",
        )
        require(
            exact_date(source.get("published_on"))
            and exact_date(source.get("retrieved_on")),
            "Publication and retrieval dates must remain explicit",
        )
        require(
            source.get("publication_precision") == "day",
            "This collection retains day-qualified publication dates",
        )
        for key in ("published_at", "modified_at", "response_saved_at"):
            val = source.get(key)
            if val is not None:
                try:
                    require(
                        text(val, 100)
                        and datetime.fromisoformat(val).tzinfo is not None,
                        "Timestamp needs an explicit offset",
                    )
                except (ValueError, TypeError, AttributeError) as exc:
                    raise ValueError("Invalid source timestamp") from exc
        require(
            source.get("published_at") is None
            or source["published_at"][:10] == source["published_on"],
            "Publication day must match the timestamp as published",
        )
        require(
            source["published_on"] <= source["retrieved_on"],
            "Retrieval cannot precede source publication",
        )
        require(
            source.get("human_review_recorded") is False
            and source.get("review_state") == REVIEW,
            "Source review remains pending",
        )
        cap = source.get("capture", {})
        require(
            isinstance(cap, dict)
            and isinstance(cap.get("sha256"), str)
            and HEX.fullmatch(cap["sha256"])
            and type(cap.get("bytes")) is int
            and cap["bytes"] > 0
            and cap.get("full_document_redistributed") is False,
            "Retain source digest, length and excerpt-only rights boundary",
        )
        require(text(source.get("rights_note")), "Source rights note is required")
        quotes = source.get("excerpts")
        require(
            isinstance(quotes, list) and 1 <= len(quotes) <= 12,
            "Retain bounded selected excerpts",
        )
        for quote in quotes:
            require(isinstance(quote, dict), "Excerpt must be an object")
            require(
                set(quote)
                == {"id", "text", "locator", "text_kind", "normalization", "sha256"}
                and text(quote.get("normalization")),
                "Excerpt must keep declared text, locator and normalization only",
            )
            qid = quote.get("id")
            require(
                isinstance(qid, str) and ID.fullmatch(qid) and qid not in excerpts,
                "Excerpt IDs must be unique",
            )
            require(
                text(quote.get("text"), 4000)
                and len(quote["text"].split()) <= 160
                and text(quote.get("locator"), 500),
                "Excerpt needs a short passage and exact locator",
            )
            require(
                quote.get("text_kind") == "exact_excerpt"
                and quote.get("sha256")
                == hashlib.sha256(quote["text"].encode("utf-8")).hexdigest(),
                "Excerpt identity must match its retained exact text",
            )
            excerpts[qid] = sid
        result[sid] = source
    return result, excerpts


def validate_refs(refs, sources, excerpts):
    require(
        isinstance(refs, list) and 1 <= len(refs) <= 12,
        "At least one source/excerpt basis is required",
    )
    for ref in refs:
        require(
            isinstance(ref, dict)
            and ref.get("source_id") in sources
            and excerpts.get(ref.get("excerpt_id")) == ref.get("source_id"),
            "Evidence reference must resolve to the correct source excerpt",
        )


def validate_study(study):
    bounded(study)
    require(
        isinstance(study, dict) and study.get("format") == FORMAT,
        "Unsupported political evidence study format",
    )
    political, media = study.get("political"), study.get("media")
    require(
        isinstance(political, dict)
        and political.get("format") == "political-developments/1",
        "Political acts require their separate contract",
    )
    require(
        isinstance(media, dict) and media.get("format") == "media-comparison-study/1",
        "Media study requires its separate contract",
    )
    p_sources, p_excerpts = source_index(political.get("sources"))
    m_sources, m_excerpts = source_index(media.get("sources"))
    require(
        not (p_sources.keys() & m_sources.keys())
        and not (p_excerpts.keys() & m_excerpts.keys()),
        "Source and excerpt identities must not collide",
    )
    sources, excerpts = p_sources | m_sources, p_excerpts | m_excerpts
    rows = political.get("developments")
    require(
        isinstance(rows, list) and 1 <= len(rows) <= 50,
        "Political collection must have one to 50 bounded acts",
    )
    ids = set()
    for row in rows:
        require(isinstance(row, dict), "Development must be an object")
        require(
            set(row)
            == {
                "id",
                "record_type",
                "title",
                "development_kind",
                "country_codes",
                "statement",
                "attribution",
                "event_time",
                "geographic_scope",
                "coordinates",
                "structured_act",
                "evidence",
                "planned_period",
                "qualifications",
                "review",
                "conflict_observation_links",
            },
            "Development contains undeclared fields",
        )
        rid = row.get("id")
        require(
            isinstance(rid, str) and ID.fullmatch(rid) and rid not in ids,
            "Development IDs must be unique",
        )
        ids.add(rid)
        require(
            row.get("record_type") == "political_development"
            and row.get("development_kind") in KINDS,
            "Do not substitute an organized-violence row or an untyped claim",
        )
        require(
            text(row.get("title"), 300) and text(row.get("statement")),
            "Development needs a bounded title and attributed statement",
        )
        require(
            isinstance(row.get("country_codes"), list)
            and 1 <= len(row["country_codes"]) <= 10
            and all(
                isinstance(v, str) and re.fullmatch("[A-Z]{2}", v)
                for v in row["country_codes"]
            ),
            "Use explicit country labels",
        )
        require(
            row.get("coordinates", "absent") is None
            and row.get("conflict_observation_links") == [],
            "This collection does not infer exact coordinates or causal conflict links",
        )
        event = row.get("event_time", {})
        require(
            isinstance(event, dict) and text(event.get("basis")),
            "Event time requires its own explicit basis",
        )
        if event.get("precision") == "unknown":
            require(
                event.get("start") is None and event.get("end") is None,
                "An unknown event date must remain null",
            )
        elif event.get("precision") == "day":
            require(
                exact_date(event.get("start"))
                and exact_date(event.get("end"))
                and event["start"] <= event["end"],
                "Event dates must be real, ordered days",
            )
        else:
            raise ValueError("Supported event precision is day or unknown")
        plan = row.get("planned_period")
        if plan is not None:
            require(
                isinstance(plan, dict)
                and plan.get("kind") == "source_reported_plan"
                and plan.get("precision") == "month",
                "Planned periods remain labelled as source-reported plans",
            )
            for key in ("start", "end"):
                value = plan.get(key)
                require(
                    isinstance(value, str)
                    and re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", value)
                    and exact_date(value + "-01"),
                    "Plan periods require real YYYY-MM values",
                )
            require(plan["start"] <= plan["end"], "Plan dates must be ordered")
        act = row.get("structured_act", {})
        require(
            isinstance(act, dict)
            and all(text(act.get(k), 500) for k in ("actor", "act", "object"))
            and act.get("evidence_status") == "source_attributed_act"
            and act.get("policy_objectives_implemented") is False
            and act.get("current_conditions_established") is False,
            "Do not promote documented acts into implementation or current-condition findings",
        )
        require(
            isinstance(row.get("qualifications"), list)
            and 1 <= len(row["qualifications"]) <= 8
            and all(text(q) for q in row["qualifications"]),
            "Retain the act's qualifications",
        )
        validate_review(row.get("review"))
        validate_refs(row.get("evidence"), p_sources, p_excerpts)
    require(
        media.get("development_id") in ids
        and text(media.get("question"), MAX_QUESTION),
        "Comparison must identify the political act and its question",
    )
    annotations = media.get("annotations")
    require(
        isinstance(annotations, list) and 1 <= len(annotations) <= 20,
        "Comparison needs bounded, typed annotations",
    )
    for item in annotations:
        require(
            isinstance(item, dict)
            and item.get("kind")
            in {"observable_text_feature", "analyst_interpretation"}
            and text(item.get("statement"))
            and text(item.get("scope")),
            "Separate textual observations from analyst interpretation",
        )
        validate_refs(item.get("basis"), sources, excerpts)
        validate_review(item.get("review"))
    lineage = media.get("lineage", {})
    require(
        isinstance(lineage, dict)
        and lineage.get("primary_document_source_id") in p_sources
        and lineage.get("shared_development_id") == media["development_id"]
        and lineage.get("independent_reporting_verified") is False
        and lineage.get("upstream_dependence_assessed") is False
        and lineage.get("publishing_entity_count")
        == len({s["publisher"] for s in m_sources.values()}),
        "Do not count publisher plurality as verified independent corroboration",
    )
    for block in (political, media):
        require(
            isinstance(block.get("boundaries"), list)
            and len(block["boundaries"]) >= 4
            and all(text(v) for v in block["boundaries"]),
            "Explicit evidence boundaries are required",
        )
    return True


def build_study(root):
    root = Path(root)
    study = {
        "format": FORMAT,
        "political": read_json(root / "data/political-developments/collection.json"),
        "media": read_json(root / "data/media-comparison/2254-adoption.json"),
    }
    validate_study(study)
    return study


def select_developments(
    study,
    ids=None,
    question="What acts are documented, what dates are known and what remains unestablished?",
):
    validate_study(study)
    require(
        text(question, MAX_QUESTION), "Provide a question of one to 2000 characters"
    )
    rows = study["political"]["developments"]
    available = [row["id"] for row in rows]
    chosen = available if ids is None else ids
    require(
        isinstance(chosen, list)
        and 1 <= len(chosen) <= 50
        and all(isinstance(v, str) and v in available for v in chosen)
        and len(set(chosen)) == len(chosen),
        "Select distinct known political-development IDs",
    )
    selected = [row for row in rows if row["id"] in chosen]
    cited = {ref["excerpt_id"] for row in selected for ref in row["evidence"]}
    retained_sources, omitted_excerpts = [], []
    for source in study["political"]["sources"]:
        quotes = [quote for quote in source["excerpts"] if quote["id"] in cited]
        omitted_excerpts.extend(
            quote["id"] for quote in source["excerpts"] if quote["id"] not in cited
        )
        if quotes:
            copy = deepcopy(source)
            copy["excerpts"] = deepcopy(quotes)
            retained_sources.append(copy)
    packet = {
        "format": SELECTION_FORMAT,
        "question": question.strip(),
        "source_snapshot_sha256": hashlib.sha256(
            canonical(study["political"])
        ).hexdigest(),
        "records": deepcopy(selected),
        "sources": retained_sources,
        "selection": {
            "available_record_ids": available,
            "retained_record_ids": [r["id"] for r in selected],
            "omitted_record_ids": [rid for rid in available if rid not in chosen],
            "retained_excerpt_ids": [
                quote["id"]
                for source in retained_sources
                for quote in source["excerpts"]
            ],
            "omitted_excerpt_ids": omitted_excerpts,
            "method": "explicit_selection",
            "note": "Source metadata is retained with cited excerpts only; omission is not an evidentiary-quality judgement.",
        },
        "boundaries": deepcopy(study["political"]["boundaries"]),
    }
    bounded(packet)
    return packet


def validate_selection(packet, study):
    bounded(packet)
    require(
        isinstance(packet, dict) and packet.get("format") == SELECTION_FORMAT,
        "Unsupported political selection format",
    )
    selection = packet.get("selection")
    require(isinstance(selection, dict), "Selection metadata is required")
    expected = select_developments(
        study, selection.get("retained_record_ids"), packet.get("question")
    )
    require(
        packet == expected,
        "Selection differs from the trusted local evidence, dates, review state or explicit omissions",
    )
    return True


def build_browser(study, output):
    """Write a same-origin static viewer and Python-prepared record selections.

    ``output`` is an HTML file path. No runtime provenance/digest or selection
    algorithm is reimplemented in the browser; JavaScript only switches records,
    renders text and downloads these already validated packets.
    """
    validate_study(study)
    output = Path(output)
    require(output.suffix.lower() == ".html", "Browser output must be an HTML file")
    assets = Path(__file__).resolve().parent / "web"
    template = (assets / "political-study.html").read_text(encoding="utf-8")
    javascript = (assets / "political-study.js").read_text(encoding="utf-8")
    css = (assets / "political-study.css").read_text(encoding="utf-8")
    require(
        template.count("__POLITICAL_STUDY_DATA__") == 1,
        "Browser template needs one data marker",
    )
    selections = {
        record["id"]: select_developments(study, [record["id"]])
        for record in study["political"]["developments"]
    }
    payload = bounded({"study": study, "selections": selections}).decode("utf-8")
    # This is a non-executable script data block. Escape every HTML-sensitive
    # character anyway so source strings cannot terminate it or create markup.
    for char, escape in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        payload = payload.replace(char, escape)
    page = template.replace("__POLITICAL_STUDY_DATA__", payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    (output.parent / "political-study.js").write_text(javascript, encoding="utf-8")
    (output.parent / "political-study.css").write_text(css, encoding="utf-8")
    return output
