from copy import deepcopy
from datetime import date
import unittest

from scripts.merge_catalogue import merge, resolve_source_id, SOURCE_ALIASES
from syria_analysis.core import canonical_url, load_workspace, read_json
from test_atlas import ROOT


class CatalogueMergeTests(unittest.TestCase):
    def setUp(self):
        self.workspace = load_workspace(ROOT)
        self.network = read_json(ROOT / 'data/sources/relationships.json')
        self.catalogue = read_json(ROOT / 'data/sources/catalogue-review.json')

    def test_complete_catalogue_provenance_and_aliases(self):
        self.assertEqual(len(self.catalogue['sources']), 25)
        self.assertEqual(len(self.catalogue['relationships']), 13)
        self.assertEqual(self.catalogue['provenance']['library_version'], 1)
        self.assertEqual(self.catalogue['provenance']['methodology_library_version'], 0)
        indexed = {s['id']: s for s in self.workspace['sources']}
        for row in self.catalogue['sources']:
            target = indexed[SOURCE_ALIASES.get(row['id'], row['id'])]
            self.assertEqual(target['catalogue_review'], row)
            self.assertEqual(target['catalogue_provenance'], self.catalogue['provenance'])
        self.assertNotIn('ap', indexed)
        self.assertNotIn('unhcr', indexed)
        self.assertNotIn('un-syria-coi', indexed)

    def test_merge_is_idempotent_and_preserves_original_research(self):
        before = deepcopy(self.workspace)
        workspace, network, additions = merge(self.workspace, self.network, self.catalogue)
        self.assertEqual(additions, [])
        self.assertEqual(workspace, before)
        self.assertEqual(network, self.network)
        self.assertEqual(self.workspace, before, 'Input is not mutated')

    def test_canonical_homepage_and_name_aliases_do_not_duplicate_outlets(self):
        indexed = {s['id']: s for s in self.workspace['sources']}
        review = deepcopy(next(s for s in self.catalogue['sources'] if s['id'] == 'ap'))
        review['id'] = 'another-ap-id'
        review['url'] = 'https://WWW.AP.ORG/about/'
        self.assertEqual(resolve_source_id(review, indexed), 'associated-press')
        review['url'] = 'https://example.org/different-path'
        review['name'] = 'Associated  Press'
        self.assertEqual(resolve_source_id(review, indexed), 'associated-press')

    def test_new_profile_merge_keeps_reviewed_records_and_feeds(self):
        original = deepcopy(self.workspace)
        original['sources'] = [s for s in original['sources'] if s['id'] != 'syria-untold']
        workspace, _, additions = merge(original, self.network, self.catalogue)
        self.assertEqual(additions, ['syria-untold'])
        for table in ('documents', 'claims', 'places', 'context', 'social_accounts'):
            self.assertEqual(workspace[table], original[table])
        old_sources = {s['id']: s for s in original['sources']}
        for source in workspace['sources']:
            if source['id'] in old_sources:
                self.assertEqual(source['feeds'], old_sources[source['id']]['feeds'])

    def test_geography_is_a_separate_relation_and_no_speculative_control(self):
        locations = {e['id'] for e in self.network['entities'] if e['type'] == 'location'}
        self.assertEqual(locations, {'damascus', 'erbil'})
        for edge in self.network['relationships']:
            if edge['target'] in locations:
                self.assertEqual(edge['type'], 'operates_in')
            self.assertNotIn(edge['type'], {'political_proxy', 'government_control', 'sdf_control'})
        north = next(s for s in self.workspace['sources'] if s['id'] == 'north-press')
        self.assertIn('Potomac', north['ownership_or_perspective']['summary'])
        self.assertIn('does not identify', north['prior_ownership_description']['summary'])

    def test_citation_urls_dates_and_evidence_ids_are_valid(self):
        for row in self.catalogue['sources']:
            date.fromisoformat(row['checked_on'])
            evidence_ids = {e['id'] for e in row['evidence']}
            for evidence in row['evidence']:
                self.assertTrue(canonical_url(evidence['url']).startswith('https://'))
                date.fromisoformat(evidence['reviewedAt'])
                if evidence.get('publishedAt'):
                    date.fromisoformat(evidence['publishedAt'])
            for ids in row['field_evidence'].values():
                self.assertTrue(set(ids) <= evidence_ids)
            for assertion in row['assertions']:
                self.assertTrue(set(assertion['evidenceIds']) <= evidence_ids)
        for source in self.workspace['sources']:
            for evidence in source['evidence']:
                canonical_url(evidence['url'])
                date.fromisoformat(evidence['checked_on'])


if __name__ == '__main__':
    unittest.main()
