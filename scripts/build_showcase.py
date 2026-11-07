"""Build only the curated public corpus; never includes the private desk database."""

import argparse
import json
from pathlib import Path

from syria_analysis import core, countries, ontology
from syria_analysis.atlas import build_atlas
from syria_analysis.context_layers import assemble, build_explorer
from syria_analysis.observations import build_observation_atlas
from syria_analysis.political_developments import build_browser, build_study


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
    observation_manifest = build_observation_atlas(root, output / "observations")
    if country["code"] == "SY":
        build_browser(build_study(root), output / "politics" / "index.html")
        (output / "politics" / "study.json").write_text(
            json.dumps(build_study(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    for page, url in (
        (output / "index.html", "observations/index.html"),
        (output / "sources/index.html", "../observations/index.html"),
    ):
        html = page.read_text(encoding="utf-8")
        link = f'<a href="{url}">Historical research atlas ↗</a>'
        if country["code"] == "SY":
            political_url = "politics/index.html" if page.parent == output else "../politics/index.html"
            link += f'<a href="{political_url}">Political acts &amp; reporting ↗</a>'
        page.write_text(
            html.replace("</header>", link + "</header>", 1), encoding="utf-8"
        )
    print(
        f"Built public snapshot in {output}: {len(pack['records'])} records; no private cases included."
    )
    print(
        "Historical atlas: "
        f"{sum(s['count'] for s in observation_manifest['event_shards']):,} event records; "
        f"{sum(s['count'] for s in observation_manifest['indicator_shards']):,} annual country values."
    )


if __name__ == "__main__":
    main()
