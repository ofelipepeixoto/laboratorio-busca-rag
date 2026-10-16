# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from studies.legislativo.core import evaluate, eligible, read_json, validate_documents, validate_cases
from studies.legislativo.fixtures import fixture


class LegislativeStudyTest(unittest.TestCase):
    def setUp(self):
        self.docs,self.cases=fixture()

    def test_fixture_replay_has_no_effects_or_approval(self):
        with patch('socket.create_connection',side_effect=AssertionError('network')):
            report=evaluate(self.docs,self.cases)
        self.assertEqual(len(self.docs),34)
        self.assertEqual(len(report['rows']),54)
        self.assertTrue(all(r['esperado']==r['obtido'] for r in report['rows']))
        self.assertFalse(report['authorization_to_execute'])
        self.assertTrue(report['synthetic_only'])
        self.assertTrue(all(r['citation']['review_status']=='pending' for r in report['rows'] if r['citation']))

    def test_family_cannot_cross_splits(self):
        self.docs[1]['split']='test'
        with self.assertRaisesRegex(ValueError,'Família'):
            validate_documents(self.docs)

    def test_identical_text_cannot_cross_splits(self):
        self.docs[8]['text']=self.docs[0]['text']
        self.docs[8]['text_sha256']=self.docs[0]['text_sha256']
        with self.assertRaisesRegex(ValueError,'Texto idêntico'):
            validate_documents(self.docs)

    def test_hash_and_duplicate_identity_are_rejected(self):
        for change in ['hash','id','version']:
            docs=copy.deepcopy(self.docs)
            if change=='hash':docs[0]['text_sha256']='0'*64
            elif change=='id':docs[1]['id']=docs[0]['id']
            else:docs[1]['version']=True
            with self.assertRaises(ValueError):validate_documents(docs)

    def test_old_future_and_wrong_kind_do_not_leak(self):
        report=evaluate(self.docs,self.cases)
        rows={r['id']:r for r in report['rows']}
        self.assertIsNone(rows['bill-not-law']['obtido'])
        self.assertIsNone(rows['wrong-house']['obtido'])
        for c in self.cases:
            if c['as_of']=='2018-01-01':self.assertIsNone(rows[c['id']]['obtido'])
            if c['expected']:
                doc=next(d for d in self.docs if d['id']==c['expected'])
                self.assertTrue(eligible(doc,c))
                self.assertTrue(doc['version']==(1 if c['as_of']=='2022-01-01' else 2))

    def test_bad_expected_reference_is_not_scored(self):
        self.cases[0]['expected']=self.docs[8]['id']
        with self.assertRaisesRegex(ValueError,'Gabarito'):evaluate(self.docs,self.cases)

    def test_overlapping_versions_and_proposed_law_rejected(self):
        self.docs[0]['valid_until']=None
        with self.assertRaisesRegex(ValueError,'sobrepostas'):validate_documents(self.docs)
        self.docs,self.cases=fixture()
        self.docs[-1]['status']='enacted'
        with self.assertRaisesRegex(ValueError,'Projeto'):validate_documents(self.docs)

    def test_json_duplicates_oversize_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json'
            for text in ['{"x":1,"x":2}',' '*(1024*1024+1),'{"x":NaN}']:
                path.write_text(text)
                with self.assertRaises(ValueError):read_json(path)
            link=Path(directory)/'link.json';link.symlink_to(path)
            with self.assertRaises(ValueError):read_json(link)

    def test_bounds_and_origin_checked(self):
        for modify in [lambda d:d.__setitem__('source_url','https://www.camara.leg.br/pretend'),lambda d:d.__setitem__('text','x'*20000)]:
            docs=copy.deepcopy(self.docs);modify(docs[0])
            with self.assertRaises(ValueError):validate_documents(docs)
        with self.assertRaises(ValueError):validate_documents(self.docs*20)

if __name__=='__main__':unittest.main()
