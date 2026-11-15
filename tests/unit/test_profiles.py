import copy
import json
import tempfile
import unittest
from pathlib import Path
from brand_threat_monitor.config.profiles import load_manifest, load_profile, validate_profile, ProfileError, read_json

ROOT = Path(__file__).resolve().parents[2]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT/'profiles/example.json').read_text(encoding='utf-8-sig'))

    def test_required_fields_and_country(self):
        for field, value in [('country', 'zz'), ('country', None), ('client_id', ''), ('enabled', 'true')]:
            profile=copy.deepcopy(self.profile)
            profile[field]=value
            with self.subTest(field=field, value=value), self.assertRaises(ProfileError):
                validate_profile(profile)

    def test_invalid_temporal_configuration(self):
        for days in [True, 0, -2, '7', 7]:
            profile=copy.deepcopy(self.profile)
            profile['days_to_review']=days
            with self.subTest(days=days), self.assertRaises(ProfileError):
                validate_profile(profile)

    def test_multiple_criteria_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            self.profile['criteria'].append({'query':'otra consulta','enabled':True})
            self.profile['criteria'].append({'query':'inactiva','enabled':False})
            (base/'profile.json').write_text(json.dumps(self.profile))
            (base/'manifest.json').write_text(json.dumps({'schema_version':'1.0',
                'profiles':[{'path':'profile.json'}, {'path':'missing.json','enabled':False}],
                'output':{'directory':'out','format':'json'}}))
            plan=load_manifest(base/'manifest.json')
            self.assertEqual(len(list(plan.queries())),2)
            self.assertEqual(plan.output_directory,base/'out')
            self.assertEqual(len(self.profile['criteria']),3)

    def test_disabled_profile_emits_no_queries(self):
        from brand_threat_monitor.config.profiles import SearchPlan
        self.profile['enabled']=False
        self.assertEqual(list(SearchPlan([validate_profile(self.profile)],ROOT).queries()),[])

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'duplicate.json'
            p.write_text('{"country":"co","country":"ec"}')
            with self.assertRaises(ProfileError):
                read_json(p)

    def test_invalid_later_profile_rejects_whole_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            (base/'good.json').write_text(json.dumps(self.profile))
            bad=copy.deepcopy(self.profile)
            del bad['country']
            (base/'bad.json').write_text(json.dumps(bad))
            (base/'manifest.json').write_text(json.dumps({'schema_version':'1.0',
                'profiles':[{'path':'good.json'},{'path':'bad.json'}]}))
            with self.assertRaises(ProfileError):
                load_manifest(base/'manifest.json')


if __name__=='__main__': unittest.main()
