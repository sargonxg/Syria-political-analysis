"""Build the pinned 2011–2025 regional UCDP GED snapshot from an official ZIP."""

import argparse
import json
from pathlib import Path

from syria_analysis.historical_events import create_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="A new output directory"
    )
    args = parser.parse_args()
    manifest = create_snapshot(args.archive, args.output)
    print(
        json.dumps(
            {
                "dataset": manifest["datasets"][0]["id"],
                "records": manifest["selection"]["retained_records"],
                "event_shards": len(manifest["event_shards"]),
                "raw_shards": len(manifest["raw_shards"]),
                "largest_shard_bytes": max(
                    row["bytes"]
                    for row in manifest["event_shards"] + manifest["raw_shards"]
                ),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
