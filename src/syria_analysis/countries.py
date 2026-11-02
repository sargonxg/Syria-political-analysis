"""Country-isolated workspaces sharing the same evidence contracts and tooling."""
from __future__ import annotations
import re
from pathlib import Path
from .core import DATA_FILES, read_json, write_json

REGISTRY = 'data/countries.json'


def country_code(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Country code must be a string')
    value = value.upper()
    if not re.fullmatch(r'[A-Z]{2}', value):
        raise ValueError('Country code must be two ASCII letters, for example SY or LB')
    return value


def registry(root: Path) -> dict:
    path = root / REGISTRY
    if not path.exists():
        # Retain legacy --root workspaces and existing CLI integrations.
        return {'schema_version': 1, 'default_country': 'SY', 'countries': [
            {'code': 'SY', 'name': 'Syria', 'region': 'Middle East', 'workspace': '.', 'status': 'legacy'}]}
    data = read_json(path)
    if data.get('schema_version') != 1 or not isinstance(data.get('countries'), list):
        raise ValueError('Invalid country registry')
    seen = set()
    for row in data['countries']:
        code = country_code(row.get('code', ''))
        if code != row['code'] or code in seen:
            raise ValueError('Duplicate or non-canonical country code')
        seen.add(code)
        if not row.get('name') or not row.get('workspace'):
            raise ValueError(f'Country {code} needs a name and workspace')
        target = (root / row['workspace']).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError(f'Country {code} workspace escapes the repository')
    if data.get('default_country') not in seen:
        raise ValueError('Default country is not registered')
    return data


def resolve(root: Path, code: str | None = None) -> tuple[Path, dict]:
    data = registry(root)
    selected = country_code(code or data['default_country'])
    row = next((r for r in data['countries'] if r['code'] == selected), None)
    if row is None:
        raise ValueError(f'Country {selected} is not registered; use init-country first')
    target = (root / row['workspace']).resolve()
    profile = {k: row[k] for k in ('code', 'name', 'region', 'status') if k in row}
    return target, profile


def initialise(root: Path, code: str, name: str, region: str) -> Path:
    code = country_code(code)
    if not name.strip() or not region.strip() or len(name) > 100 or len(region) > 100:
        raise ValueError('Provide a country name and region, each at most 100 characters')
    data = registry(root)
    if any(row['code'] == code for row in data['countries']):
        raise ValueError(f'Country {code} is already registered; no data changed')
    target = (root / 'countries' / code.lower()).resolve()
    if not target.is_relative_to(root.resolve()) or target.exists():
        raise ValueError('Country directory already exists or is outside the repository')
    # Empty by design: extending the framework does not manufacture research.
    for filename in DATA_FILES.values():
        write_json(target / filename, [])
    write_json(target / 'data/coverage/lexicon.json', {
        'version': 1, 'country_name': name.strip(), 'topics': [], 'places': []})
    write_json(target / 'data/coverage/comparisons.json', [])
    write_json(target / 'data/ontology/module.json', {
        'schema_version': 1, 'version': '1.0.0', 'country_code': code,
        'title': f'{name.strip()} political research vocabulary',
        'status': 'empty_framework', 'concepts': [], 'references': []})
    write_json(target / 'data/ontology/entities.json', [])
    write_json(target / 'data/ontology/assertions.json', [])
    write_json(target / 'data/ontology/reviews.json', [])
    row = {'code': code, 'name': name.strip(), 'region': region.strip(),
           'workspace': target.relative_to(root.resolve()).as_posix(), 'status': 'empty_framework'}
    write_json(target / 'data/country.json', row)
    data['countries'].append(row)
    write_json(root / REGISTRY, data)
    return target
