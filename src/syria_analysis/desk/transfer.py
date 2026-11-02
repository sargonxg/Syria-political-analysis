"""Validated, transactional offline case restoration; never an HTTP upload route."""

import json

from ..core import valid_datetime
from .models import CaseWrite, RecordWrite
from .store import Conflict


def restore_case(store, bundle):
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("Expected a version 1 case export")
    case = bundle.get("case", {})
    CaseWrite.model_validate({"title": case.get("title")})
    if (
        not isinstance(case.get("id"), str)
        or not 1 <= len(case["id"]) <= 200
        or not valid_datetime(case.get("created_at"))
        or not case.get("created_at")
    ):
        raise ValueError("Case identity and creation time are required")
    records = bundle.get("records")
    revisions = bundle.get("revisions")
    if (
        not isinstance(records, list)
        or not isinstance(revisions, list)
        or len(records) > 10000
        or len(revisions) > 100000
    ):
        raise ValueError("Invalid or oversized record/revision lists")
    indexed, models = {}, {}
    allowed = set(RecordWrite.model_fields) | {
        "id",
        "case_id",
        "revision",
        "created_at",
        "updated_at",
        "provenance",
        "citation_provenance",
    }

    def validate_row(row):
        if (
            not isinstance(row, dict)
            or set(row) - allowed
            or row.get("case_id") != case["id"]
        ):
            raise ValueError("Record has unexpected fields or belongs to another case")
        rid = row.get("id")
        if (
            not isinstance(rid, str)
            or not 1 <= len(rid) <= 200
            or type(row.get("revision")) is not int
            or row["revision"] < 1
        ):
            raise ValueError("Invalid record identity or revision")
        if any(
            not row.get(k) or not valid_datetime(row[k])
            for k in ("created_at", "updated_at")
        ):
            raise ValueError("Record timestamps must include timezone information")
        model = RecordWrite.model_validate(
            {k: v for k, v in row.items() if k in RecordWrite.model_fields}
        )
        if model.source_id and model.kind != "document":
            raise ValueError("Only documents may have publisher references")
        return model

    for row in records:
        model = validate_row(row)
        if row["id"] in indexed:
            raise ValueError("Duplicate record IDs")
        indexed[row["id"]], models[row["id"]] = row, model
    edges = set()
    for rid, model in models.items():
        for target in model.links:
            edges.add((rid, target, "references"))
        if model.source_id:
            if (
                models.get(model.source_id) is None
                or models[model.source_id].kind != "source"
            ):
                raise ValueError("Document publisher is missing or not a source")
            edges.add((rid, model.source_id, "published_by"))
        if model.document_id:
            doc = models.get(model.document_id)
            if doc is None or doc.kind != "document" or model.excerpt not in doc.body:
                raise ValueError("Claim citation does not match a stored document")
            edges.add((rid, model.document_id, "cites_excerpt_from"))
    if any(a == b or a not in indexed or b not in indexed for a, b, _ in edges):
        raise ValueError("Dangling or self-referencing links")
    supplied_edges = bundle.get("relationships")
    if not isinstance(supplied_edges, list) or any(
        not isinstance(e, dict) or set(e) != {"source", "target", "relation"}
        for e in supplied_edges
    ):
        raise ValueError("Malformed relationship records")
    actual = {(e["source"], e["target"], e["relation"]) for e in supplied_edges}
    if actual != edges or len(actual) != len(supplied_edges):
        raise ValueError(
            "Relationship records do not match the exported record references"
        )
    history = {}
    for row in revisions:
        validate_row(row)
        if row["id"] not in indexed or row["kind"] != indexed[row["id"]]["kind"]:
            raise ValueError(
                "Revision belongs to an unknown record or changes its type"
            )
        key = (row["id"], row["revision"])
        if key in history:
            raise ValueError("Duplicate revision snapshot")
        history[key] = row
    for rid, row in indexed.items():
        if (
            any((rid, n) not in history for n in range(1, row["revision"] + 1))
            or history.get((rid, row["revision"])) != row
        ):
            raise ValueError(
                "Incomplete history or latest snapshot differs from the current record"
            )
        if any(rid == key[0] and key[1] > row["revision"] for key in history):
            raise ValueError("History extends beyond current revision")
    for row in revisions:
        if row["kind"] == "claim":
            citation = row.get("citation_provenance") or {}
            version = history.get(
                (row["document_id"], citation.get("document_revision"))
            )
            if (
                not version
                or row["excerpt"] not in version["body"]
                or citation.get("excerpt") != row["excerpt"]
                or citation.get("locator") != row["locator"]
            ):
                raise ValueError(
                    "Claim history lacks its cited document revision and exact passage"
                )
    with store.connection() as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM cases WHERE id=?", (case["id"],)).fetchone():
            raise Conflict(
                "Case ID already exists; restore into a clean database instead of overwriting"
            )
        if any(
            con.execute("SELECT 1 FROM records WHERE id=?", (rid,)).fetchone()
            for rid in indexed
        ):
            raise Conflict("A record ID already exists in this database")
        con.execute(
            "INSERT INTO cases VALUES(?,?,?)",
            (case["id"], case["title"], case["created_at"]),
        )
        for row in records:
            payload = {
                k: v
                for k, v in row.items()
                if k not in {"id", "case_id", "revision", "created_at", "updated_at"}
            }
            con.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["case_id"],
                    row["kind"],
                    row["title"],
                    row["body"],
                    json.dumps(payload, ensure_ascii=False),
                    row["revision"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        con.executemany("INSERT INTO links VALUES(?,?,?)", sorted(edges))
        con.executemany(
            "INSERT INTO revisions VALUES(?,?,?,?)",
            [
                (
                    r["id"],
                    r["revision"],
                    json.dumps(r, ensure_ascii=False),
                    r["updated_at"],
                )
                for r in revisions
            ],
        )
    return case["id"]
