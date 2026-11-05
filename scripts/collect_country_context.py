#!/usr/bin/env python3
"""Explicit manual refresh of the bounded historical country-context snapshot."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from syria_analysis.country_context import collect_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Fresh directory; existing snapshots are never overwritten",
    )
    parser.add_argument("--start-year", type=int, default=1960)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    try:
        manifest = collect_snapshot(
            args.output, start_year=args.start_year, end_year=args.end_year
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Country-context collection refused: {error}\n")
    print(
        f"Saved {manifest['observation_count']:,} non-null annual values; {manifest['null_value_count']:,} null rows kept separately; {manifest['indicator_count']} indicators, {len(manifest['economies'])} economies."
    )
    print(f"Source updated {manifest['source_last_updated']}; snapshot: {args.output}")


if __name__ == "__main__":
    main()
