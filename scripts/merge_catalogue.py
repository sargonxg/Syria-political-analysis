"""Merge the reviewed Library text input without replacing existing research records.

Run from the repository with PYTHONPATH=src. This is an explicit, offline maintenance
operation; it does not retrieve files or certify the input's assertions.
"""
from copy import deepcopy
from pathlib import Path
import re
from urllib.parse import urlsplit

from syria_analysis.core import graph, load_workspace, read_json, validate, write_json
from syria_analysis.atlas import validate_relationships

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ALIASES = {'ap': 'associated-press', 'un-syria-coi': 'coi-syria', 'unhcr': 'unhcr-syria'}
ENTITY_ALIASES = {'sy-information-ministry': 'syrian-information-ministry'}
CATEGORIES = {'official': 'state_media', 'international': 'international_wire',
              'rights-monitoring': 'advocacy_monitoring', 'un-primary': 'official_reporting',
              'regional': 'regional_media'}
RELATION_EQUIVALENTS = {'institutional_affiliation': 'ministry_affiliation',
                         'owned_by': 'stated_legal_owner'}
RELATION_LABELS = {'institutional_affiliation': 'States institutional affiliation',
                  'operates_in': 'Disclosed operating location', 'operated_by': 'States operator',
                  'owned_by': 'States legal owner', 'business_unit_of': 'Business unit of',
                  'part_of': 'Part of institution / group'}


def homepage_key(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or '').casefold().removeprefix('www.')
    return host, parsed.path.rstrip('/').casefold()


def name_key(value):
    return re.sub(r'[^\w]', '', value.casefold())


def resolve_source_id(review, by_id):
    preferred = SOURCE_ALIASES.get(review['id'], review['id'])
    if preferred in by_id:
        return preferred
    for source in by_id.values():
        if homepage_key(source['url']) == homepage_key(review['url']):
            return source['id']
        if name_key(source['name']) == name_key(review['name']):
            return source['id']
    return preferred


def merge(workspace, network, catalogue):
    workspace, network = deepcopy(workspace), deepcopy(network)
    by_id = {s['id']: s for s in workspace['sources']}
    additions = []
    resolved_ids = {}
    for review in catalogue['sources']:
        sid = resolve_source_id(review, by_id)
        resolved_ids[review['id']] = sid
        if sid not in by_id:
            source = {'id': sid, 'name': review['name'], 'url': review['url'],
                      'type': CATEGORIES.get(review['category'], 'syrian_local_media'),
                      'entity_kind': 'organization', 'languages': review['languages'],
                      'scope': review['coverage'], 'description': review['editorial_focus'],
                      'ownership_or_perspective': {'summary': review['ownership_funding']['summary'],
                          'attribution': 'Attributed public organizational evidence; not an independent audit.'},
                      'strengths': [f"Reading focus: {review['editorial_focus']}"],
                      'limits': review['qualifications']['caveats'] + [review['language_scope']],
                      'evidence': [], 'feeds': [], 'feed_status': 'No feed verified in this catalogue review',
                      'checked_on': review['checked_on']}
            workspace['sources'].append(source)
            by_id[sid] = source
            additions.append(sid)
        source = by_id[sid]
        source['catalogue_review'] = deepcopy(review)
        source['catalogue_provenance'] = deepcopy(catalogue['provenance'])
        urls = {e['url'] for e in source['evidence']}
        for evidence in review['evidence']:
            if evidence['url'] not in urls:
                source['evidence'].append({'title': evidence['title'], 'url': evidence['url'],
                    'basis': 'Relevant reviewed public evidence; consult the qualification and assertion records for scope.',
                    'kind': evidence['basis'], 'access': 'catalogue_text_review',
                    'checked_on': evidence['reviewedAt'], 'catalogue_evidence_id': evidence['id']})
                urls.add(evidence['url'])
        if sid == 'north-press' and 'prior_ownership_description' not in source:
            source['prior_ownership_description'] = deepcopy(source['ownership_or_perspective'])
            source['ownership_or_perspective']['summary'] = review['ownership_funding']['summary']
            source['ownership_update_note'] = 'Earlier Arabic-page review did not establish ownership. The additional English About-page review names a legal owner; beneficial ownership and funding shares remain unestablished.'
    entity_ids = {s['id'] for s in workspace['sources']} | {e['id'] for e in network['entities']}
    for entity in catalogue['entities']:
        eid = ENTITY_ALIASES.get(entity['id'], entity['id'])
        if eid not in entity_ids:
            network['entities'].append(entity | {'id': eid})
            entity_ids.add(eid)
    def signature(edge):
        return edge['source'], edge['target'], RELATION_EQUIVALENTS.get(edge['type'], edge['type'])
    existing = {signature(r): r for r in network['relationships']}
    entity_names = {e['id']: e['name'] for e in workspace['sources'] + network['entities']}
    for edge in catalogue['relationships']:
        sid = resolved_ids.get(edge['source'], SOURCE_ALIASES.get(edge['source'], edge['source']))
        target = ENTITY_ALIASES.get(edge['target'], edge['target'])
        record = {'id': edge['id'], 'source': sid, 'target': target, 'type': edge['type'],
                  'label': RELATION_LABELS[edge['type']], 'basis': edge['evidenceBasis'],
                  'statement': f"{by_id[sid]['name']}: {RELATION_LABELS[edge['type']].lower()} {entity_names[target]}.",
                  'evidence': [{'url': url, 'locator': 'Reviewed organizational / mandate page',
                                'checked_on': edge['verifiedAt']} for url in edge['evidenceUrls']],
                  'checked_on': edge['verifiedAt'], 'valid_from': None, 'valid_to': None,
                  'caveat': edge['caveat'], 'catalogue_provenance': deepcopy(catalogue['provenance'])}
        match = existing.get(signature(record))
        if match:
            urls = {e['url'] for e in match['evidence']}
            match['evidence'].extend(e for e in record['evidence'] if e['url'] not in urls)
            match['catalogue_provenance'] = deepcopy(catalogue['provenance'])
        else:
            network['relationships'].append(record)
            existing[signature(record)] = record
    errors = validate(workspace)
    if errors:
        raise ValueError('; '.join(errors))
    validate_relationships(workspace, network)
    return workspace, network, additions


def main():
    catalogue = read_json(ROOT / 'data/sources/catalogue-review.json')
    workspace, network, additions = merge(load_workspace(ROOT), read_json(ROOT / 'data/sources/relationships.json'), catalogue)
    write_json(ROOT / 'data/sources/registry.json', workspace['sources'])
    write_json(ROOT / 'data/sources/relationships.json', network)
    categories = read_json(ROOT / 'data/sources/categories.json')
    if not any(c['id'] == 'regional_media' for c in categories):
        categories.append({'id': 'regional_media', 'label': 'Regional media', 'count': 0})
    for category in categories:
        category['count'] = sum(s['type'] == category['id'] for s in workspace['sources'])
    write_json(ROOT / 'data/sources/categories.json', categories)
    manifest = read_json(ROOT / 'data/manifest.json')
    manifest['counts']['sources'] = len(workspace['sources'])
    manifest['graph'] = {key: len(value) for key, value in graph(workspace).items() if key in ('nodes', 'edges')}
    manifest['catalogue_input'] = catalogue['provenance']
    write_json(ROOT / 'data/manifest.json', manifest)
    provenance = read_json(ROOT / 'data/sources/provenance.json')
    provenance['coverage_note'] = f"{len(workspace['sources'])} selected entities; {len(network['relationships'])} documented organizational/location relationships. Curated coverage, not a live connection or exhaustive catalogue."
    provenance['catalogue_input'] = catalogue['provenance']
    write_json(ROOT / 'data/sources/provenance.json', provenance)
    print(f"Merged catalogue: {len(additions)} new sources; {len(workspace['sources'])} total; {len(network['relationships'])} relationships")


if __name__ == '__main__':
    main()
