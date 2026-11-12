"""Build or validate a bounded context packet from local UTF-8 text; never fetch a URL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from syria_analysis.document_workshop import (
    MAX_PACKET_BYTES,
    build_packet,
    canonical_bytes,
    decode_json,
    evaluate_fixture,
    read_bounded,
    validate_packet,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text", type=Path, help="UTF-8 .txt/.md file, at most 128 KiB"
    )
    parser.add_argument("--title", default="Local document")
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--published-on", default=None)
    parser.add_argument("--question")
    parser.add_argument(
        "--select", nargs="+", help="Explicit paragraph IDs such as p001 p003"
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Optional local JSON array of visitor-entered annotations",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/document-workshop/selection.json")
    )
    parser.add_argument(
        "--validate",
        type=Path,
        help="Check packet against supplied original --text and metadata; writes nothing",
    )
    parser.add_argument(
        "--evaluate",
        type=Path,
        help="Run explicit synthetic paragraph-rubric fixture; no model evaluation",
    )
    args = parser.parse_args(argv)
    try:
        if args.evaluate:
            value = evaluate_fixture(decode_json(read_bounded(args.evaluate)))
        else:
            if not args.text:
                parser.error("--text is required unless --evaluate is used")
            if args.text.suffix.lower() not in {".txt", ".md", ".markdown"}:
                parser.error("--text accepts .txt, .md or .markdown files only")
            text = read_bounded(args.text)
            source = {
                "title": args.title,
                "uri": args.source_url,
                "published_on": args.published_on,
            }
            annotations = (
                decode_json(read_bounded(args.annotations)) if args.annotations else []
            )
            if args.validate:
                packet = decode_json(read_bounded(args.validate, MAX_PACKET_BYTES))
                validate_packet(packet, text, source, annotations)
                print(
                    "Valid policy-document-workshop/1; exact local source, selection and measurements agree."
                )
                return 0
            if not args.question or not args.select:
                parser.error("--question and --select are required to build a packet")
            value = build_packet(text, source, args.question, args.select, annotations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_bytes(value))
        print(
            f"Wrote {args.output}; no network or model call. Source text and annotations remain unverified."
        )
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(2, f"Document workshop failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
