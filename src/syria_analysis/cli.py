"""Local command-line workflows; all collection is explicit and manual."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from .core import brief, context_pack, csv_exports, graph, load_workspace, validate, write_json
from .feeds import collect
from .social import import_reference

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
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate', help='Validate IDs, provenance and review/location boundaries')
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
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        workspace = load_workspace(root)
        errors = validate(workspace)
        if errors: raise ValueError('\n'.join(errors))
        if args.command == 'validate':
            print('Valid: ' + ', '.join(f'{len(rows)} {name}' for name, rows in workspace.items()))
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
            pack = context_pack(workspace); write_json(args.output, pack)
            args.jsonl.parent.mkdir(parents=True, exist_ok=True)
            lines = [{'record_type': 'manifest', **{k: pack[k] for k in ('schema_version', 'generated_at', 'use_rules', 'limitations')}}]
            lines += [{'table': table, 'record': row} for table, rows in workspace.items() for row in rows]
            args.jsonl.write_text(''.join(json.dumps(line, ensure_ascii=False) + '\n' for line in lines), encoding='utf-8')
            print(f'Wrote context to {args.output} and {args.jsonl}')
        elif args.command == 'brief':
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(brief(workspace, args.question, args.place, args.analyst_note), encoding='utf-8')
            print(f'Wrote source assembly to {args.output}; analyst assessment remains separate.')
        elif args.command == 'export-graph':
            path = args.output or Path('exports/evidence.' + ('json' if args.format == 'json' else 'graphml'))
            data = graph(workspace)
            if args.format == 'json': write_json(path, data)
            else:
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(graphml(data), encoding='utf-8')
            print(f"Wrote {len(data['nodes'])} nodes and {len(data['edges'])} typed edges to {path}")
        elif args.command == 'export-csv':
            csv_exports(workspace, args.output); print(f'Wrote CSV tables to {args.output}')
        elif args.command == 'build-atlas':
            from .atlas import build_atlas
            from .core import read_json
            relationships_path = root / 'data/sources/relationships.json'
            relationships = read_json(relationships_path) if relationships_path.exists() else None
            path = build_atlas(workspace, args.output, relationships)
            print(f'Wrote offline source atlas to {path}; open it in a browser. No live collection is enabled.')
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
