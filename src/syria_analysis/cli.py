"""Local command-line workflows; all collection is explicit and manual."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from .core import brief, context_pack, csv_exports, graph, load_workspace, validate, write_json, read_json
from .coverage import build_coverage
from .feeds import collect
from .social import import_reference
from .countries import registry, resolve, initialise
from .ontology import build_model, jsonld

def graphml(data: dict) -> str:
    ns = 'http://graphml.graphdrawing.org/xmlns'
    ET.register_namespace('', ns)
    root = ET.Element(f'{{{ns}}}graphml')
    for name, scope in [('label', 'node'), ('type', 'node'), ('relation', 'edge')]:
        ET.SubElement(root, f'{{{ns}}}key', {'id': name, 'for': scope, 'attr.name': name, 'attr.type': 'string'})
    body = ET.SubElement(root, f'{{{ns}}}graph', {'id': 'evidence', 'edgedefault': 'directed'})
    for node in data['nodes']:
        entry = ET.SubElement(body, f'{{{ns}}}node', {'id': node['id']})
        for key in ('label', 'type'): ET.SubElement(entry, f'{{{ns}}}data', {'key': key}).text = node[key]
    for i, edge in enumerate(data['edges']):
        entry = ET.SubElement(body, f'{{{ns}}}edge', {'id': f'e{i}', 'source': edge['source'], 'target': edge['target']})
        ET.SubElement(entry, f'{{{ns}}}data', {'key': 'relation'}).text = edge['relation']
    return ET.tostring(root, encoding='unicode', xml_declaration=True) + '\n'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Repository/data workspace root (default: current directory)')
    parser.add_argument('--country', help='Registered two-letter country code; defaults to the registry default')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate', help='Validate IDs, provenance and review/location boundaries')
    commands.add_parser('countries', help='List registered countries and actual collection status')
    country = commands.add_parser('init-country', help='Create an empty isolated country workspace; no research is copied')
    country.add_argument('--code', required=True); country.add_argument('--name', required=True)
    country.add_argument('--region', required=True)
    political = commands.add_parser('ontology', help='Export controlled terms and qualified political assertions')
    political.add_argument('--format', choices=['json', 'jsonld'], default='json')
    political.add_argument('--output', type=Path)
    layered = commands.add_parser('context-layers', help='Assemble seven evidence/ontology/method layers and an offline explorer')
    layered.add_argument('--question', required=True)
    layered.add_argument('--publication-cutoff', help='Publication date only, YYYY-MM-DD; not a historical knowledge cutoff')
    layered.add_argument('--format', choices=['json', 'html', 'markdown'], default='json')
    layered.add_argument('--output', type=Path)
    feeds = commands.add_parser('collect-rss', help='Refresh verified RSS/Atom references; preserves reviewed records')
    feeds.add_argument('--source', action='append', help='Source id; repeat to select several')
    feeds.add_argument('--limit', type=int, default=6)
    social = commands.add_parser('import-post', help='Register a post URL only; does not fetch post text')
    social.add_argument('--url', required=True); social.add_argument('--note', default='')
    context = commands.add_parser('build-context'); context.add_argument('--output', type=Path, default=Path('exports/context.json'))
    context.add_argument('--jsonl', type=Path, default=Path('exports/context.jsonl'))
    briefing = commands.add_parser('brief'); briefing.add_argument('--question', required=True)
    briefing.add_argument('--place'); briefing.add_argument('--analyst-note', default='')
    briefing.add_argument('--output', type=Path, default=Path('exports/brief.md'))
    network = commands.add_parser('export-graph'); network.add_argument('--format', choices=['json', 'graphml'], default='json')
    network.add_argument('--output', type=Path)
    csv = commands.add_parser('export-csv'); csv.add_argument('--output', type=Path, default=Path('exports/csv'))
    atlas = commands.add_parser('build-atlas', help='Build a self-contained offline interactive source atlas')
    atlas.add_argument('--output', type=Path, default=Path('exports/atlas/index.html'))
    compare = commands.add_parser('compare-sources', help='Build a source-qualified media framing worksheet, without outlet scores')
    compare.add_argument('--left', required=True); compare.add_argument('--right', required=True)
    compare.add_argument('--question', required=True); compare.add_argument('--format', choices=['json','markdown'], default='json')
    compare.add_argument('--output', type=Path, default=Path('output/comparison.json'))
    commands.add_parser('resources', help='List dated research resource references and access prerequisites')
    coverage = commands.add_parser('coverage', help='Build transparent source/title/topic/place-mention coverage data')
    coverage.add_argument('--output', type=Path, default=Path('exports/coverage.json'))
    args = parser.parse_args(argv)
    try:
        repository = args.root.resolve()
        if args.command == 'countries':
            for row in registry(repository)['countries']:
                print(f"{row['code']}\t{row['name']}\t{row.get('region', '')}\t{row.get('status', 'unknown')}")
            return 0
        if args.command == 'init-country':
            target = initialise(repository, args.code, args.name, args.region)
            print(f'Created empty framework at {target}; no sources, claims or political facts were copied.')
            return 0
        root, country = resolve(repository, args.country)
        # Relative exports stay inside the selected country's workspace.
        for name in ('output', 'jsonl'):
            path = getattr(args, name, None)
            if path is not None and not path.is_absolute():
                setattr(args, name, root / path)
        workspace = load_workspace(root)
        errors = validate(workspace)
        if errors: raise ValueError('\n'.join(errors))
        model = build_model(repository, root, workspace, country)
        if args.command == 'validate':
            print(f"Valid {country['code']}: " + ', '.join(f'{len(rows)} {name}' for name, rows in workspace.items()))
            if model:
                print(f"Political model: {len(model['entities'])} entities, {len(model['assertions'])} qualified assertions, {len(model['module']['concepts'])} concepts")
        elif args.command == 'context-layers':
            from .context_layers import assemble, build_explorer, markdown
            pack = assemble(workspace, model, country, args.question, args.publication_cutoff)
            suffix = {'json': 'json', 'html': 'html', 'markdown': 'md'}[args.format]
            path = args.output or root / ('exports/context-layers.' + suffix)
            if args.format == 'html':
                build_explorer(pack, path)
            elif args.format == 'markdown':
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(markdown(pack), encoding='utf-8')
            else:
                write_json(path, pack)
            print(f"Wrote {len(pack['records'])} source-qualified records in seven layers to {path}")
        elif args.command == 'collect-rss':
            if not 1 <= args.limit <= 30: raise ValueError('Limit must be between 1 and 30 per endpoint')
            known = {s['id'] for s in workspace['sources']}
            if args.source and set(args.source) - known: raise ValueError('Unknown source id')
            result = collect(workspace['sources'], args.limit, args.source)
            if not any(feed['status'] == 'parsed' for feed in result['feeds']):
                raise ValueError('All selected feeds were unavailable; stored data has not changed')
            # New receipts cannot overwrite a record reviewed by an analyst.
            merged = {d['id']: d for d in workspace['documents']}
            for doc in result['items']:
                if doc['id'] not in merged or merged[doc['id']]['review_state'] == 'unreviewed_reference': merged[doc['id']] = doc
            candidate = workspace | {'documents': list(merged.values())}
            errors = validate(candidate)
            if errors: raise ValueError('; '.join(errors))
            write_json(root / 'data/documents/receipts.json', candidate['documents'])
            write_json(root / 'data/documents/collection-run.json', {k: v for k, v in result.items() if k != 'items'})
            print(f"Collected {len(result['items'])} unreviewed references; {sum(f['status'] == 'parsed' for f in result['feeds'])}/{len(result['feeds'])} endpoints parsed.")
        elif args.command == 'import-post':
            row = import_reference(args.url, workspace['social_accounts'], args.note)
            merged = {r['id']: r for r in workspace['social_references']}; merged[row['id']] = row
            write_json(root / 'data/social/references.json', list(merged.values()))
            print(f"Registered {row['id']}; no content fetched or geographic inference made.")
        elif args.command == 'build-context':
            import json
            pack = context_pack(workspace, country)
            if model:
                pack['political_context'] = model
            write_json(args.output, pack)
            args.jsonl.parent.mkdir(parents=True, exist_ok=True)
            lines = [{'record_type': 'manifest', **{k: pack[k] for k in ('schema_version', 'generated_at', 'country', 'use_rules', 'limitations')}}]
            lines += [{'table': table, 'record': row} for table, rows in workspace.items() for row in rows]
            if model:
                lines[0]['political_use_rules'] = model['use_rules']
                lines[0]['ontology_version'] = model['core']['version']
                lines[0]['political_module'] = {k: model['module'][k] for k in ('version', 'country_code', 'title', 'status')}
                lines += [{'table': 'ontology_' + table, 'record': row}
                          for table in ('classes', 'relations') for row in model['core'][table]]
                lines += [{'table': 'political_concepts', 'country_code': country['code'], 'record': row}
                          for row in model['module']['concepts']]
                lines += [{'table': 'political_' + table, 'country_code': country['code'], 'record': row}
                          for table in ('entities', 'assertions') for row in model[table]]
            args.jsonl.write_text(''.join(json.dumps(line, ensure_ascii=False) + '\n' for line in lines), encoding='utf-8')
            print(f'Wrote context to {args.output} and {args.jsonl}')
        elif args.command == 'brief':
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(brief(workspace, args.question, args.place, args.analyst_note), encoding='utf-8')
            print(f'Wrote source assembly to {args.output}; analyst assessment remains separate.')
        elif args.command == 'export-graph':
            path = args.output or root / ('exports/evidence.' + ('json' if args.format == 'json' else 'graphml'))
            data = graph(workspace)
            if args.format == 'json': write_json(path, data)
            else:
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(graphml(data), encoding='utf-8')
            print(f"Wrote {len(data['nodes'])} nodes and {len(data['edges'])} typed edges to {path}")
        elif args.command == 'export-csv':
            csv_exports(workspace, args.output); print(f'Wrote CSV tables to {args.output}')
        elif args.command == 'build-atlas':
            from .atlas import build_atlas
            relationships_path = root / 'data/sources/relationships.json'
            relationships = read_json(relationships_path) if relationships_path.exists() else None
            resources_path = root / 'data/sources/resources.json'
            resources = read_json(resources_path) if resources_path.exists() else None
            path = build_atlas(workspace, args.output, relationships, resources)
            print(f'Wrote offline source atlas to {path}; open it in a browser. No live collection is enabled.')
        elif args.command == 'compare-sources':
            from .media_assessment import comparison, markdown
            pack = comparison(workspace, args.left, args.right, args.question)
            if args.format == 'json': write_json(args.output, pack)
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(markdown(pack), encoding='utf-8')
            print(f'Wrote unreviewed media comparison to {args.output}; no outlet score generated.')
        elif args.command == 'resources':
            import json
            path = root / 'data/sources/resources.json'
            print(json.dumps(read_json(path) if path.exists() else {'profiles': []}, ensure_ascii=False, indent=2))
        elif args.command == 'coverage':
            data = build_coverage(workspace, read_json(root / 'data/coverage/lexicon.json'))
            write_json(args.output, data)
            print(f"Wrote coverage for {len(data['references'])} saved references; no event coordinates inferred.")
        elif args.command == 'ontology':
            if model is None:
                raise ValueError('No political module in this legacy workspace; register a country module first')
            path = args.output or root / ('exports/political-context.' + args.format)
            write_json(path, jsonld(model) if args.format == 'jsonld' else model)
            print(f"Wrote {len(model['assertions'])} qualified political assertions to {path}; no bare political fact triples emitted.")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
