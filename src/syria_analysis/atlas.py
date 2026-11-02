"""Build a portable, offline source atlas from the validated research workspace."""
from __future__ import annotations

import json
from pathlib import Path

from datetime import date
from .core import canonical_url, graph, now_utc, validate


def validate_relationships(workspace: dict, network: dict) -> None:
    """Reject unsourced or dangling institutional links before publication."""
    known = {row['id'] for row in workspace['sources']}
    for entity in network.get('entities', []):
        if not entity.get('id') or entity['id'] in known:
            raise ValueError('Relationship entity IDs must be unique')
        known.add(entity['id'])
    ids = set()
    allowed = {'ministry_affiliation', 'listed_group_company', 'stated_legal_owner',
               'research_programme_of', 'institutional_role', 'institutional_affiliation',
               'operates_in', 'operated_by', 'owned_by', 'business_unit_of', 'part_of'}
    for edge in network.get('relationships', []):
        if not edge.get('id') or edge['id'] in ids:
            raise ValueError('Relationship IDs must be unique')
        ids.add(edge['id'])
        if edge.get('source') not in known or edge.get('target') not in known:
            raise ValueError('Relationship has an unknown endpoint')
        if edge.get('type') not in allowed or not edge.get('basis') or not edge.get('caveat') or not edge.get('evidence'):
            raise ValueError('Relationship needs an allowed type, evidence basis and caveat')
        date.fromisoformat(edge['checked_on'])
        for evidence in edge['evidence']:
            canonical_url(evidence['url'])
            date.fromisoformat(evidence['checked_on'])
        for key in ('valid_from', 'valid_to'):
            if edge.get(key) is not None:
                date.fromisoformat(edge[key])


def build_atlas(workspace: dict, output: Path, relationships: dict | None = None) -> Path:
    """Embed data and assets; opening the result makes no network requests."""
    errors = validate(workspace)
    if errors:
        raise ValueError('; '.join(errors))
    relationships = relationships or {'entities': [], 'relationships': []}
    validate_relationships(workspace, relationships)
    assets = Path(__file__).parent / 'web'
    payload = {'schema_version': 1, 'built_at': now_utc(), **workspace,
               'graph': graph(workspace), 'relationships': relationships}
    # Script-data contexts require escaping '<', including hostile closing tags.
    data = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html = (assets / 'index.html').read_text(encoding='utf-8')
    html = html.replace('/* ATLAS_CSS */', (assets / 'atlas.css').read_text(encoding='utf-8'))
    html = html.replace('/* ATLAS_JS */', (assets / 'atlas.js').read_text(encoding='utf-8'))
    html = html.replace('/* ATLAS_DATA */', data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    return output
