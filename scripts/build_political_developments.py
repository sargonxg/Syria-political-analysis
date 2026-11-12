"""Build or validate the small source-qualified political/media worked study offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from syria_analysis.political_developments import (
    build_browser,
    build_study,
    read_json,
    select_developments,
    validate_selection,
    validate_study,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--html",
        type=Path,
        help="Optional HTML file path for the same-origin static study",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/political-evidence"
    )
    parser.add_argument(
        "--ids", nargs="+", help="Explicit political-development IDs to retain"
    )
    parser.add_argument(
        "--question",
        default="What acts are documented, what dates are known and what remains unestablished?",
    )
    parser.add_argument(
        "--validate",
        type=Path,
        help="Validate a study or selection against this checkout; writes nothing",
    )
    args = parser.parse_args(argv)
    try:
        study = build_study(args.root)
        if args.validate:
            packet = read_json(args.validate)
            if not isinstance(packet, dict):
                raise ValueError("Evidence must be a JSON object")
            if packet.get("format") == "political-evidence-study/1":
                validate_study(packet)
                if packet != study:
                    raise ValueError(
                        "Study differs from this checkout's retained evidence"
                    )
            elif packet.get("format") == "political-developments/1":
                validate_study({**study, "political": packet})
                if packet != study["political"]:
                    raise ValueError(
                        "Political collection differs from this checkout's evidence"
                    )
            elif packet.get("format") == "media-comparison-study/1":
                validate_study({**study, "media": packet})
                if packet != study["media"]:
                    raise ValueError(
                        "Media comparison differs from this checkout's evidence"
                    )
            else:
                validate_selection(packet, study)
            print(
                "Valid political evidence: source/excerpt references, dates, pending review and evidence boundaries agree."
            )
            return 0
        selection = select_developments(study, args.ids, args.question)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, item in (
            ("study.json", study),
            ("developments.json", study["political"]),
            ("media-comparison.json", study["media"]),
            ("selection.json", selection),
        ):
            (args.output / name).write_text(
                json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        if args.html:
            build_browser(study, args.html)
        print(
            f"Built {args.output}: {len(study['political']['developments'])} political records and one two-item media comparison; no network or model calls."
        )
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"Political evidence build failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
