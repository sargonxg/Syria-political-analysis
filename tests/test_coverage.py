import unittest
from pathlib import Path
from syria_analysis.core import load_workspace, read_json
from syria_analysis.coverage import build_coverage, matched_terms

ROOT = Path(__file__).resolve().parents[1]
class CoverageTests(unittest.TestCase):
    def test_multilingual_matches_retain_literal_evidence(self):
        self.assertEqual(matched_terms('Legal outreach in Daraa', ['Daraa', 'war']), ['Daraa'])
        self.assertEqual(matched_terms('أعمال في درعا', ['درعا']), ['درعا'])
        self.assertEqual(matched_terms('reward and artwork', ['war', 'art']), [])

    def test_unknown_topic_and_place_stay_unknown(self):
        workspace = load_workspace(ROOT)
        row = next(d for d in workspace['documents'] if d['review_state'] == 'unreviewed_reference')
        row['title'] = 'A reference without a known place or keyword'
        value = build_coverage(workspace, read_json(ROOT / 'data/coverage/lexicon.json'))
        result = next(r for r in value['references'] if r['id'] == row['id'])
        self.assertEqual(result['topic_matches'], [])
        self.assertEqual(result['place_mentions'], [])
        self.assertIsNone(result['coordinates'])
        self.assertEqual(row['review_state'], 'unreviewed_reference')

    def test_graph_has_provenance_and_no_dangling_relationships(self):
        value = build_coverage(load_workspace(ROOT), read_json(ROOT / 'data/coverage/lexicon.json'))
        ids = {n['id'] for n in value['graph']['nodes']}
        for edge in value['graph']['edges']:
            self.assertIn(edge['source'], ids); self.assertIn(edge['target'], ids)
            self.assertIn(edge['relation'], ['published_reference', 'title_keyword_match', 'title_place_mention'])
        self.assertTrue(any(s['reference_count'] == 0 and s['status'].startswith('Directory only') for s in value['sources']))
if __name__ == '__main__': unittest.main()
