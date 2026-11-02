from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from syria_analysis.atlas import build_atlas, validate_relationships
from syria_analysis.cli import main
from syria_analysis.core import load_workspace

ROOT = Path(__file__).resolve().parents[1]


class AtlasParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data = ''
        self.in_data = False
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.scripts += 1
            self.in_data = dict(attrs).get('id') == 'atlas-data'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_data = False

    def handle_data(self, text):
        if self.in_data:
            self.data += text


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.workspace = load_workspace(ROOT)

    def test_build_preserves_all_records_without_remote_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = build_atlas(self.workspace, Path(directory) / 'atlas/index.html')
            html = output.read_text(encoding='utf-8')
            parsed = AtlasParser()
            parsed.feed(html)
            payload = json.loads(parsed.data)
            self.assertEqual(payload['sources'], self.workspace['sources'])
            self.assertEqual(payload['claims'], self.workspace['claims'])
            self.assertEqual(parsed.scripts, 2)
            self.assertNotIn('/* ATLAS_', html)
            self.assertIn("connect-src 'none'", html)
            self.assertNotIn('<script src=', html)
            self.assertNotIn('<link rel="stylesheet"', html)

    def test_script_breakout_and_html_payload_remain_inert_data(self):
        data = deepcopy(self.workspace)
        payload = '</script><script>alert("x")</script><img src=x onerror=alert(1)> /* ATLAS_JS */'
        data['sources'][0]['description'] = payload
        with tempfile.TemporaryDirectory() as directory:
            html = build_atlas(data, Path(directory) / 'index.html').read_text(encoding='utf-8')
            parsed = AtlasParser()
            parsed.feed(html)
            self.assertEqual(parsed.scripts, 2)
            self.assertEqual(json.loads(parsed.data)['sources'][0]['description'], payload)
            self.assertNotIn(payload, html)

    def test_invalid_workspace_never_overwrites_existing_output(self):
        self.workspace['documents'][0]['source_id'] = 'unknown'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.html'
            path.write_text('preserve this', encoding='utf-8')
            with self.assertRaises(ValueError):
                build_atlas(self.workspace, path)
            self.assertEqual(path.read_text(encoding='utf-8'), 'preserve this')

    def test_cli_builds_atlas_from_explicit_root(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.html'
            self.assertEqual(main(['--root', str(ROOT), 'build-atlas', '--output', str(path)]), 0)
            self.assertTrue(path.is_file())

    def test_relationships_reject_dangling_unsourced_and_inferred_edges(self):
        network = json.loads((ROOT / 'data/sources/relationships.json').read_text(encoding='utf-8'))
        validate_relationships(self.workspace, network)
        for field, value in [('source', 'imagined-source'), ('evidence', []), ('type', 'political_proxy'), ('checked_on', 'not-a-date')]:
            modified = deepcopy(network)
            modified['relationships'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_relationships(self.workspace, modified)

    def test_manifest_and_category_counts_match_the_corpus(self):
        manifest = json.loads((ROOT / 'data/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['counts']['sources'], len(self.workspace['sources']))
        categories = json.loads((ROOT / 'data/sources/categories.json').read_text(encoding='utf-8'))
        for category in categories:
            self.assertEqual(category['count'], sum(s['type'] == category['id'] for s in self.workspace['sources']))


if __name__ == '__main__':
    unittest.main()
