"""Offline database maintenance. No collection or external service calls."""

import argparse
import json
from pathlib import Path

from ..core import load_workspace
from .models import RecordWrite
from .store import Store, now


def import_public(store, root):
    key = "public-syria-corpus-v1"
    with store.connection() as con:
        if con.execute("SELECT 1 FROM imports WHERE import_key=?", (key,)).fetchone():
            return False
    case_id = "public-syria-research"
    if not any(c["id"] == case_id for c in store.cases()):
        store.create_case("Syria / imported public research", case_id)
    data = load_workspace(root)
    for s in data["sources"]:
        rid = "public-source-" + s["id"]
        try:
            store.get(rid)
        except KeyError:
            store.write(
                case_id,
                RecordWrite(
                    kind="source",
                    title=s["name"],
                    body=s["description"] + "\n\n" + "\n".join(s["limits"]),
                    url=s["url"],
                    reviewed_on=s["checked_on"],
                    tags=["public-import", s["type"]],
                ),
                rid,
                metadata=s,
            )
    for d in data["documents"]:
        rid = "public-document-" + d["id"]
        try:
            store.get(rid)
        except KeyError:
            store.write(
                case_id,
                RecordWrite(
                    kind="document",
                    title=d["title"],
                    url=d["url"],
                    source_id="public-source-" + d["source_id"],
                    published_on=d.get("published_on")
                    or (d.get("published_at") or "")[:10]
                    or None,
                    tags=["public-import", d["review_state"]],
                    body=d.get("original_passage") or "",
                ),
                rid,
                metadata=d,
            )
    for c in data["claims"]:
        rid = "public-paraphrase-" + c["id"]
        try:
            store.get(rid)
        except KeyError:
            store.write(
                case_id,
                RecordWrite(
                    kind="note",
                    title=c["id"],
                    body=c["statement"]
                    + "\n\nQualification: "
                    + c["qualification"]
                    + "\n\nImported attributed paraphrase. No original source excerpt is bundled; this is not a newly verified claim.",
                    links=[
                        "public-document-" + e["document_id"] for e in c["evidence"]
                    ],
                    tags=["public-import", "attributed-paraphrase"],
                ),
                rid,
                metadata=c,
            )
    for topic in data["context"]:
        rid = "public-theme-" + topic["id"]
        try:
            store.get(rid)
        except KeyError:
            store.write(
                case_id,
                RecordWrite(
                    kind="theme",
                    title=topic["title"],
                    body=topic["summary"],
                    tags=["public-import"],
                    links=["public-source-" + sid for sid in topic["source_ids"]],
                ),
                rid,
                metadata=topic,
            )
    with store.connection() as con:
        con.execute("INSERT OR IGNORE INTO imports VALUES(?,?)", (key, now()))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("revoke-sessions")
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    seed = sub.add_parser("import-public")
    seed.add_argument("--root", type=Path, default=Path.cwd())
    restore = sub.add_parser("restore-case")
    restore.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    store = Store(args.database)
    if args.command == "backup":
        store.backup(args.output)
        print("Consistent SQLite backup created; keep it private.")
    elif args.command == "restore-case":
        from .transfer import restore_case

        if args.input.stat().st_size > 50_000_000:
            raise ValueError("Case input exceeds the 50 MB offline import limit")
        case_id = restore_case(
            store, json.loads(args.input.read_text(encoding="utf-8"))
        )
        print(f"Restored case {case_id}; IDs, references and revisions preserved.")
    elif args.command == "revoke-sessions":
        with store.connection() as con:
            con.execute("DELETE FROM sessions")
        print("All desk sessions revoked; rotate the operator access key separately.")
    elif args.command == "import-public":
        print(
            "Public corpus imported."
            if import_public(store, args.root)
            else "This import was already completed; analyst edits preserved."
        )
    else:
        print("Database migration complete.")


if __name__ == "__main__":
    main()
