"""Build the small public policy-document lab and bounded packets, entirely offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Runnable directly from a checkout, without installing a package or dependencies.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from syria_analysis.policy_document import (
    TASKS,
    build_lab,
    build_selection,
    load_corpus,
    parse_selection,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository containing the three public curated input files",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/policy-document-20261107"
    )
    parser.add_argument(
        "--task", choices=[task["id"] for task in TASKS], default="negotiations"
    )
    parser.add_argument(
        "--question",
        help="Optional question label, maximum 2000 characters; does not trigger retrieval or generation",
    )
    parser.add_argument(
        "--select",
        nargs="+",
        metavar="ASSERTION_ID",
        help="One to six explicit assertion IDs; no automatic relevance ranking",
    )
    parser.add_argument(
        "--validate",
        type=Path,
        help="Validate a bounded packet against the retained local curated corpus; writes nothing",
    )
    args = parser.parse_args(argv)
    try:
        corpus = load_corpus(args.root)
        if args.validate:
            with args.validate.open("rb") as handle:
                from syria_analysis.policy_document import MAX_PACKET_BYTES

                packet = parse_selection(handle.read(MAX_PACKET_BYTES + 1), *corpus)
            print(
                f"Valid {packet['format']}; canonical evidence, selection, provenance and byte measurements agree."
            )
            return 0
        packet = build_selection(
            *corpus,
            args.task,
            selected_record_ids=args.select,
            question=args.question,
        )
        lab = build_lab(*corpus)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, value in [("lab.json", lab), ("selection.json", packet)]:
            (args.output / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        for task in lab["tasks"]:
            (args.output / f"{task['id']}.json").write_text(
                json.dumps(
                    task["packet"], ensure_ascii=False, indent=2, allow_nan=False
                )
                + "\n",
                encoding="utf-8",
            )
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Policy-document build failed: {exc}\n")
    print(
        f"Built {args.output}: three selected primary excerpts, six unchanged normative drafts and three predefined tasks; no network or model calls."
    )
    print(
        "Evidence-byte comparisons exclude the question and packet envelope, and do not measure full-PDF coverage or tokens."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
