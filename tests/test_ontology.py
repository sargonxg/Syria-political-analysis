from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from jsonschema import Draft202012Validator, FormatChecker
from pyld import jsonld as processor
from syria_analysis import core, countries, ontology
from syria_analysis.cli import main

ROOT = Path(__file__).resolve().parents[1]


class PoliticalModelTests(unittest.TestCase):
    def setUp(self):
        self.workspace = core.load_workspace(ROOT)
        self.country = countries.resolve(ROOT, 'SY')[1]
        self.model = ontology.build_model(ROOT, ROOT, self.workspace, self.country)

    def errors(self):
        m = self.model
        return ontology.validate_model(m['core'], m['module'], m['entities'], m['assertions'], self.workspace, self.country, m['review_activities'])

    def test_committed_model_contracts_and_primary_source_locators(self):
        self.assertEqual(self.errors(), [])
        pairs = [('political_core', self.model['core']), ('political_module', self.model['module']),
                 ('political_entities', self.model['entities']), ('political_assertions', self.model['assertions']),
                 ('countries', core.read_json(ROOT / 'data/countries.json')), ('political_reviews', self.model['review_activities'])]
        for name, data in pairs:
            schema = core.read_json(ROOT / f'schemas/{name}.schema.json')
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)
        self.assertEqual(len(self.model['assertions']), 6)
        for row in self.model['assertions']:
            self.assertEqual(row['temporal_scope']['source_statement_on'], '2015-12-18')
            self.assertFalse(row['human_review_recorded'])
            self.assertEqual(row['review_state'], 'needs_source_check')
            self.assertIn('Operative paragraph', row['evidence'][0]['locator'])

    def test_normative_expression_cannot_become_implementation(self):
        self.model['assertions'][0]['modality']['implementation_asserted'] = True
        self.assertTrue(any('cannot assert implementation' in e for e in self.errors()))

    def test_unknown_relations_and_wrong_entity_types_are_rejected(self):
        self.model['assertions'][0]['relation_id'] = 'politically_controls'
        self.assertTrue(any('unknown subject, relation or object' in e for e in self.errors()))
        self.model['assertions'][0]['relation_id'] = 'requests'
        self.model['entities'][0]['type'] = 'PublicPerson'
        self.assertTrue(any('domain/range mismatch' in e for e in self.errors()))

    def test_unreviewed_headline_is_not_political_evidence(self):
        headline = next(d for d in self.workspace['documents'] if d['review_state'] == 'unreviewed_reference')
        self.model['assertions'][0]['evidence'] = [{'document_id': headline['id'], 'locator': 'Title'}]
        self.assertTrue(any('unreviewed headline' in e for e in self.errors()))

    def test_cross_country_assertions_and_false_human_review_are_rejected(self):
        row = self.model['assertions'][0]
        row['country_code'] = 'LB'
        self.assertTrue(any('country mismatch' in e for e in self.errors()))
        row['country_code'] = 'SY'; row['human_review_recorded'] = True
        row['review_activity_id'] = 'invented-human-review'
        self.assertTrue(any('human-review provenance' in e for e in self.errors()))

    def test_corroboration_requires_source_independence(self):
        row = self.model['assertions'][0]
        row['review_state'] = 'corroborated'; row['evidence'] *= 2
        self.assertTrue(any('independent publishers' in e for e in self.errors()))

    def test_evidence_publisher_and_registered_url_are_checked(self):
        row = self.model['assertions'][0]['evidence'][0]
        row['source_id'] = 'unhcr-syria'; row['source_url'] = 'https://example.org/unregistered'
        self.assertTrue(any('publisher mismatch' in e for e in self.errors()))
        self.assertTrue(any('URL not registered' in e for e in self.errors()))

    def test_actual_roles_require_role_specific_qualifiers(self):
        row = self.model['assertions'][0]
        self.model['entities'][0]['type'] = 'InstitutionOrOrganization'
        self.model['entities'][1]['type'] = 'PoliticalProcess'
        row['relation_id'] = 'mediates'; row['modality']['kind'] = 'reported_action'
        self.assertTrue(any('requires role_basis' in e for e in self.errors()))

    def test_jsonld_expands_offline_and_preserves_qualified_not_bare_triples(self):
        expanded = processor.expand(ontology.jsonld(self.model))
        nodes = {node['@id']: node for node in expanded}
        prefix = 'urn:policy-analysis:SY:'
        assertion = nodes[prefix + 'assertion:' + self.model['assertions'][0]['id']]
        self.assertIn('http://www.w3.org/1999/02/22-rdf-syntax-ns#Statement', assertion['@type'])
        self.assertEqual(assertion[ontology.POLICY + 'humanReviewRecorded'][0]['@value'], False)
        self.assertTrue(assertion[ontology.POLICY + 'qualification'])
        self.assertIn(ontology.POLICY + 'temporalScope', assertion)
        for row in self.model['assertions']:
            subject = nodes[prefix + 'entity:' + row['subject_id']]
            self.assertNotIn(ontology.POLICY + row['relation_id'], subject)
        doc = self.model['documents'][0]
        source, receipt = nodes[doc['url']], nodes[prefix + 'document:' + doc['id']]
        self.assertIn('http://purl.org/dc/terms/issued', source)
        self.assertNotIn('http://purl.org/dc/terms/issued', receipt)
        self.assertIn(ontology.POLICY + 'retrievedAt', receipt)

    def test_context_exports_include_country_and_political_records(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            self.assertEqual(main(['--root', str(ROOT), '--country', 'SY', 'build-context', '--output', str(dest/'context.json'), '--jsonl', str(dest/'context.jsonl')]), 0)
            pack = core.read_json(dest/'context.json')
            self.assertEqual(pack['country']['code'], 'SY')
            self.assertEqual(len(pack['political_context']['assertions']), 6)
            rows = [json.loads(line) for line in (dest/'context.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(sum(row.get('table') == 'political_assertions' for row in rows), 6)


class CountryWorkspaceTests(unittest.TestCase):
    def fixture(self, root):
        shutil.copytree(ROOT/'data', root/'data')
        shutil.copytree(ROOT/'ontology', root/'ontology')

    def test_new_country_stays_empty_and_exports_to_its_own_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            self.assertEqual(main(['--root', str(root), 'init-country', '--code', 'LB', '--name', 'Lebanon', '--region', 'Middle East']), 0)
            target, profile = countries.resolve(root, 'lb')
            data = core.load_workspace(target)
            self.assertTrue(all(not rows for rows in data.values()))
            self.assertEqual(len(core.load_workspace(root)['documents']), 44)
            self.assertEqual(profile['status'], 'empty_framework')
            self.assertEqual(main(['--root', str(root), '--country', 'LB', 'validate']), 0)
            self.assertEqual(main(['--root', str(root), '--country', 'LB', 'build-context']), 0)
            pack = core.read_json(target/'exports/context.json')
            self.assertEqual(pack['country']['code'], 'LB')
            self.assertFalse(pack['political_context']['assertions'])
            self.assertFalse((root/'exports/context.json').exists())
            self.assertEqual(main(['--root', str(root), '--country', 'LB', 'coverage']), 0)
            coverage = core.read_json(target/'exports/coverage.json')
            self.assertEqual(coverage['title'], 'Lebanon source-coverage sample')
            self.assertEqual(coverage['references'], [])

    def test_duplicate_initialisation_preserves_existing_country_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            before = (root/'data/documents/receipts.json').read_bytes()
            with self.assertRaises(ValueError): countries.initialise(root, 'SY', 'Syria', 'Middle East')
            self.assertEqual((root/'data/documents/receipts.json').read_bytes(), before)

    def test_unknown_country_and_path_escape_fail_without_falling_back_to_syria(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            with self.assertRaises(ValueError): countries.resolve(root, 'LB')
            data = core.read_json(root/'data/countries.json')
            data['countries'][0]['workspace'] = '../outside'
            core.write_json(root/'data/countries.json', data)
            with self.assertRaises(ValueError): countries.resolve(root, 'SY')
            for code in ['../SY', 'S Y', 'S', 4]:
                with self.assertRaises(ValueError): countries.country_code(code)


if __name__ == '__main__':
    unittest.main()
