"""Build only the curated public corpus; never includes the private desk database."""

import argparse
import json
from pathlib import Path

from syria_analysis import core, countries, ontology
from syria_analysis.atlas import build_atlas
from syria_analysis.context_layers import assemble, build_explorer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--country", default="SY")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    workspace_root, country = countries.resolve(root, args.country)
    workspace = core.load_workspace(workspace_root)
    model = ontology.build_model(root, workspace_root, workspace, country)
    pack = assemble(
        workspace,
        model,
        country,
        "What does resolution 2254 request, and which implementation questions need separate evidence?"
        if country["code"] == "SY"
        else "Which sources and evidence does this country workspace need?",
    )
    output = args.output.resolve()
    build_explorer(pack, output / "index.html")
    (output / "context-layers.json").write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Atlas generation is deliberately separate from private case exports.
    relationships_path = workspace_root / "data/sources/relationships.json"
    relationships = (
        core.read_json(relationships_path) if relationships_path.exists() else None
    )
    resources_path = workspace_root / "data/sources/resources.json"
    resources = core.read_json(resources_path) if resources_path.exists() else None
    build_atlas(workspace, output / "sources" / "index.html", relationships, resources)
    print(
        f"Built public snapshot in {output}: {len(pack['records'])} records; no private cases included."
    )


if __name__ == "__main__":
    main()
