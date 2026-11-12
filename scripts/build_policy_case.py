"""Build, search or reopen a local policy-document knowledge case. Never fetch a URL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from syria_analysis.document_knowledge import (
    evaluate_selection,
    jsonld,
    normalize_federal_register,
    read_json,
    reopen,
    require,
    search,
    select_context,
    validate_model,
    write_database,
)
from syria_analysis.document_knowledge_view import viewer
from syria_analysis.document_workshop import canonical_bytes, read_bounded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        type=Path,
        default=ROOT / "data/policy-case/eo-14179",
        help="Directory with document.txt, receipt.json and model.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output/policy-case",
        help="New directory; never overwritten",
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="Reopen a local database read-only instead of building",
    )
    parser.add_argument("--task", default="action-plan")
    parser.add_argument("--search")
    parser.add_argument("--max-bytes", type=int, default=64000)
    args = parser.parse_args(argv)
    try:
        if args.database:
            text, source, model = reopen(args.database)
            result = (
                search(args.database, args.search)
                if args.search
                else select_context(text, source, model, args.task, args.max_bytes)
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        receipt = read_json(args.case / "receipt.json")
        model = read_json(args.case / "model.json")
        text = read_bounded(args.case / "document.txt")
        require(
            hashlib.sha256(text.encode()).hexdigest() == receipt["normalized_sha256"],
            "Normalized source hash mismatch",
        )
        # Only the bundled Federal Register example has this narrowly defined normalizer.
        raw = None
        if receipt.get("document_id") == "us-eo-14179-2025":
            with (args.case / "source.html").open("rb") as handle:
                raw = handle.read(256 * 1024 + 1)
            require(
                hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Raw source hash mismatch",
            )
            require(
                normalize_federal_register(raw) == text,
                "Normalization differs from committed source",
            )
        source = {key: receipt[key] for key in ["title", "uri", "published_on"]}
        types = {x["id"] for x in read_json(ROOT / "ontology/core.json")["classes"]}
        paragraphs, _ = validate_model(text, source, model, types)
        contexts = {
            t["id"]: select_context(text, source, model, t["id"], args.max_bytes)
            for t in model["tasks"]
        }
        evaluations = {
            t["id"]: evaluate_selection(text, source, model, t["id"])
            for t in model["tasks"]
        }
        output = args.output.absolute()
        require(
            not any(p.is_symlink() for p in [output, *output.parents]),
            "Output cannot traverse symlinks",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(mode=0o700, exist_ok=False)

        def save(name, value):
            dest = output / name
            with dest.open("xb") as handle:
                os.chmod(dest, 0o600)
                handle.write(
                    value if isinstance(value, bytes) else value.encode("utf-8")
                )

        save("document.txt", text)
        save("receipt.json", canonical_bytes(receipt))
        save("model.json", canonical_bytes(model))
        if raw is not None:
            save("source.html", raw)
        save("graph.jsonld", canonical_bytes(jsonld(text, source, model)))
        save("evaluation.json", canonical_bytes(evaluations))
        save("index.html", viewer(text, receipt, model, contexts, evaluations))
        (output / "contexts").mkdir(mode=0o700)
        for key, value in contexts.items():
            save(f"contexts/{key}.json", canonical_bytes(value))
            save(f"contexts/{key}.txt", value["prompt"])
        write_database(output / "research.sqlite3", text, source, model)
        reopen(output / "research.sqlite3")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "source_bytes": len(text.encode()),
                    "stored_text_blocks": len(paragraphs),
                    "draft_assertions": len(model["assertions"]),
                    "tasks": len(contexts),
                    "network_calls": 0,
                    "model_calls": 0,
                    "reopen_verified": True,
                },
                indent=2,
            )
        )
    except (ValueError, OSError, KeyError, TypeError, sqlite3.DatabaseError) as exc:
        parser.exit(2, f"Policy case refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
