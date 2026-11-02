"""SQLite persistence, forward-only migrations and bounded case exports."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 1
MIGRATION_1 = """
CREATE TABLE cases(id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE records(
 id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), kind TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT NOT NULL, revision INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX record_case_kind ON records(case_id, kind);
CREATE TABLE links(source TEXT REFERENCES records(id), target TEXT REFERENCES records(id),
 relation TEXT NOT NULL, PRIMARY KEY(source,target,relation));
CREATE TABLE revisions(record_id TEXT REFERENCES records(id), revision INTEGER NOT NULL,
 snapshot TEXT NOT NULL, changed_at TEXT NOT NULL, PRIMARY KEY(record_id,revision));
CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL);
CREATE TABLE login_attempts(peer TEXT PRIMARY KEY, failures INTEGER NOT NULL, reset_at REAL NOT NULL);
CREATE TABLE imports(import_key TEXT PRIMARY KEY, imported_at TEXT NOT NULL);
"""


def now():
    return datetime.now(UTC).isoformat()


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def migrate(self):
        with self.connection() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError(
                    "Database schema is newer than this application; restore matching code"
                )
            if version == 0:
                con.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + MIGRATION_1
                    + "\nPRAGMA user_version=1; COMMIT;"
                )
            con.execute("PRAGMA journal_mode=WAL")

    def cases(self):
        with self.connection() as con:
            return [
                dict(r)
                for r in con.execute("SELECT * FROM cases ORDER BY created_at,id")
            ]

    def create_case(self, title, case_id=None):
        row = {"id": case_id or str(uuid4()), "title": title, "created_at": now()}
        with self.connection() as con:
            con.execute("INSERT INTO cases VALUES(:id,:title,:created_at)", row)
        return row

    @staticmethod
    def unpack(row):
        return json.loads(row["payload"]) | {
            k: row[k]
            for k in (
                "id",
                "case_id",
                "kind",
                "title",
                "body",
                "revision",
                "created_at",
                "updated_at",
            )
        }

    def get(self, rid):
        with self.connection() as con:
            row = con.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
            if row is None:
                raise KeyError("Record not found")
            result = self.unpack(row)
            result["backlinks"] = [
                dict(r)
                for r in con.execute(
                    "SELECT r.id,r.title,r.kind,l.relation FROM links l JOIN records r ON r.id=l.source WHERE l.target=? ORDER BY r.title",
                    (rid,),
                )
            ]
            return result

    def records(self, case_id, query="", kind="", offset=0, limit=50):
        # LIKE is deliberately literal, not SQL or a user-supplied full-text expression.
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where = "case_id=? AND (?='' OR kind=?) AND (?='' OR title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' OR payload LIKE ? ESCAPE '\\')"
        args = (
            case_id,
            kind,
            kind,
            query,
            f"%{escaped}%",
            f"%{escaped}%",
            f"%{escaped}%",
        )
        with self.connection() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM records WHERE " + where, args
            ).fetchone()[0]
            rows = con.execute(
                "SELECT * FROM records WHERE "
                + where
                + " ORDER BY updated_at DESC,id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
        return {
            "items": [self.unpack(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    def write(self, case_id, record, rid=None, expected_revision=None, metadata=None):
        payload = record.model_dump(mode="json")
        rid = rid or str(uuid4())
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if (
                con.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone()
                is None
            ):
                raise KeyError("Case not found")
            previous = con.execute(
                "SELECT * FROM records WHERE id=?", (rid,)
            ).fetchone()
            if expected_revision is not None and (
                previous is None or previous["revision"] != expected_revision
            ):
                raise Conflict(
                    "This record changed. Reload it before saving; your draft has not been overwritten."
                )
            if previous and previous["case_id"] != case_id:
                raise ValueError("A record cannot move between cases")
            if previous and previous["kind"] != record.kind:
                raise ValueError("Record type is immutable")
            references = [
                (link, "references", None) for link in dict.fromkeys(record.links)
            ]
            if record.source_id:
                if record.kind != "document":
                    raise ValueError("Source references belong to documents")
                references.append((record.source_id, "published_by", "source"))
            if record.document_id:
                references.append(
                    (record.document_id, "cites_excerpt_from", "document")
                )
            for target, _, kind in references:
                row = con.execute(
                    "SELECT * FROM records WHERE id=? AND case_id=?", (target, case_id)
                ).fetchone()
                if target == rid or row is None or (kind and row["kind"] != kind):
                    raise ValueError(
                        "References must point to a matching record in the same case"
                    )
                if target == record.document_id and record.excerpt not in row["body"]:
                    raise ValueError(
                        "The exact claim excerpt must occur in the stored document text"
                    )
                if target == record.document_id:
                    document_payload = json.loads(row["payload"])
                    payload["citation_provenance"] = {
                        "document_id": target,
                        "document_revision": row["revision"],
                        "document_url": document_payload.get("url"),
                        "source_id": document_payload.get("source_id"),
                        "published_on": document_payload.get("published_on"),
                        "reviewed_on": document_payload.get("reviewed_on"),
                        "excerpt": record.excerpt,
                        "locator": record.locator,
                    }
            # A document edit cannot silently invalidate an already cited passage.
            if record.kind == "document":
                for row in con.execute(
                    "SELECT r.payload FROM links l JOIN records r ON r.id=l.source WHERE l.target=? AND l.relation='cites_excerpt_from'",
                    (rid,),
                ):
                    if json.loads(row["payload"])["excerpt"] not in record.body:
                        raise Conflict(
                            "This edit removes an excerpt cited by a claim; revise the claim first"
                        )
            revision = previous["revision"] + 1 if previous else 1
            payload["provenance"] = (
                json.loads(previous["payload"]).get("provenance")
                if previous
                else metadata
            )
            created = previous["created_at"] if previous else now()
            updated = now()
            con.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,payload=excluded.payload,revision=excluded.revision,updated_at=excluded.updated_at",
                (
                    rid,
                    case_id,
                    record.kind,
                    record.title,
                    record.body,
                    json.dumps(payload, ensure_ascii=False),
                    revision,
                    created,
                    updated,
                ),
            )
            con.execute("DELETE FROM links WHERE source=?", (rid,))
            con.executemany(
                "INSERT OR IGNORE INTO links VALUES(?,?,?)",
                [(rid, target, relation) for target, relation, _ in references],
            )
            snapshot = payload | {
                "id": rid,
                "case_id": case_id,
                "revision": revision,
                "created_at": created,
                "updated_at": updated,
            }
            con.execute(
                "INSERT INTO revisions VALUES(?,?,?,?)",
                (rid, revision, json.dumps(snapshot, ensure_ascii=False), updated),
            )
        return self.get(rid)

    def history(self, rid):
        self.get(rid)
        with self.connection() as con:
            return [
                json.loads(r["snapshot"])
                for r in con.execute(
                    "SELECT snapshot FROM revisions WHERE record_id=? ORDER BY revision DESC",
                    (rid,),
                )
            ]

    def export(self, case_id):
        case = next((c for c in self.cases() if c["id"] == case_id), None)
        if case is None:
            raise KeyError("Case not found")
        with self.connection() as con:
            rows = con.execute(
                "SELECT * FROM records WHERE case_id=? ORDER BY id", (case_id,)
            ).fetchall()
            if len(rows) > 10000:
                raise ValueError(
                    "Case exceeds the 10,000-record export limit; use an administrator database backup"
                )
            records = [self.unpack(r) for r in rows]
            edges = [
                dict(r)
                for r in con.execute(
                    "SELECT l.* FROM links l JOIN records r ON l.source=r.id WHERE r.case_id=? ORDER BY l.source,l.target,l.relation",
                    (case_id,),
                )
            ]
            revisions = [
                json.loads(r["snapshot"])
                for r in con.execute(
                    "SELECT h.snapshot FROM revisions h JOIN records r ON r.id=h.record_id WHERE r.case_id=? ORDER BY h.record_id,h.revision",
                    (case_id,),
                )
            ]
        return {
            "schema_version": 1,
            "exported_at": now(),
            "case": case,
            "records": records,
            "relationships": edges,
            "revisions": revisions,
            "qualification": "Analyst-authored workspace; confidence is a documented judgment, not an outlet reliability score. Export excludes login sessions.",
        }

    def backup(self, destination):
        destination = Path(destination)
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ValueError(
                "Backup destination must be a new file distinct from the live database"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with (
            self.connection() as source,
            closing(sqlite3.connect(destination)) as target,
        ):
            source.backup(target)
