"""Focused regressions from review 9931439. Uses local HTTP, never GitHub Actions."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser
import policy
import receipt
import target
A, B = 'a' * 40, 'b' * 40


class LocalAPI(unittest.TestCase):
    def setUp(self):
        self.calls = []; self.post_code = 201
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                owner.calls.append(('GET', self.path, None))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'object': {'sha': A}}).encode())
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append(('POST', self.path, data))
                owner.auth = self.headers['Authorization']
                self.send_response(owner.post_code); self.end_headers()
                self.wfile.write(json.dumps({'state': data['state']}).encode())
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.env = patch.dict(os.environ, {'GH_TOKEN': 'LOCAL_TEST_ONLY',
            'GITHUB_API_URL': f'http://127.0.0.1:{self.server.server_port}',
            'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_RUN_ID': '123'})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_manual_target_independent_of_controller(self):
        self.assertEqual(target.resolve('owner/repo', 'feat/p4-vente-caisse', A), A)
        self.assertEqual(self.calls[0][1], '/repos/owner/repo/git/ref/heads/feat/p4-vente-caisse')

    def test_target_changed_before_start_is_rejected(self):
        with self.assertRaises(ValueError): target.resolve('owner/repo', 'feat/p4-vente-caisse', B)

    def test_invalid_manual_branch_or_sha_makes_no_http_call(self):
        for branch, sha in [('main', 'short'), ('../main', A), ('', A)]:
            with self.assertRaises((ValueError, __import__('subprocess').CalledProcessError)):
                target.resolve('owner/repo', branch, sha)
        self.assertEqual(self.calls, [])

    def test_real_http_status_payload_on_exact_sha(self):
        receipt.status('owner/repo', A, 'pending', 'Recette en attente')
        method, path, data = self.calls[-1]
        self.assertEqual((method, path), ('POST', '/repos/owner/repo/statuses/' + A))
        self.assertEqual(data['context'], 'neosys/recette-complete')
        self.assertEqual(data['state'], 'pending')
        self.assertEqual(self.auth, 'Bearer LOCAL_TEST_ONLY')
        self.assertTrue(data['target_url'].endswith('/owner/repo/actions/runs/123'))

    def test_http_permission_denial_is_not_reported_as_success(self):
        self.post_code = 403
        with self.assertRaises(urllib.error.HTTPError):
            receipt.status('owner/repo', A, 'success', 'Test refusé')

    def test_actual_http_finish_skipped_required_job_never_publishes_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p / 'event').write_text('{}')
            for skipped in ('postgres', 'postgres_34'):
                results = dict(sqlite='success', postgres='success', postgres_34='success', browser='success')
                results[skipped] = 'skipped'
                env = dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_EVENT_PATH=str(p/'event'),
                    GITHUB_REPOSITORY='owner/repo', TESTED_SHA=A, ACTUAL_SHA=A, FULL='true',
                    TARGET_BRANCH='feat/p4-vente-caisse', GITHUB_REF='refs/heads/main',
                    GITHUB_STEP_SUMMARY=str(p/'summary'), JOB_RESULTS=json.dumps(results))
                with self.subTest(skipped=skipped), patch.dict(os.environ, env), \
                        patch.object(sys, 'argv', ['receipt.py','finish']):
                    with self.assertRaises(SystemExit): receipt.main()
                    self.assertEqual(self.calls[-1][2]['state'], 'failure')
                    self.assertEqual(self.calls[0][1], '/repos/owner/repo/git/ref/heads/feat/p4-vente-caisse')
                    self.calls.clear()

    def test_actual_http_complete_finish_publishes_green_on_target_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'event').write_text('{}')
            env=dict(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_EVENT_PATH=str(p/'event'),
                GITHUB_REPOSITORY='owner/repo',TESTED_SHA=A,ACTUAL_SHA=A,FULL='true',
                TARGET_BRANCH='feat/p4-vente-caisse',GITHUB_REF='refs/heads/main',
                GITHUB_STEP_SUMMARY=str(p/'summary'),
                JOB_RESULTS=json.dumps(dict(sqlite='success',postgres='success',postgres_34='success',browser='success')))
            with patch.dict(os.environ,env),patch.object(sys,'argv',['receipt.py','finish']): receipt.main()
            self.assertEqual(self.calls[-1][1],'/repos/owner/repo/statuses/'+A)
            self.assertEqual(self.calls[-1][2]['state'],'success')
            self.assertEqual(self.calls[-1][2]['context'],'neosys/recette-complete')

    def test_manual_plan_records_distinct_target_and_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'event').write_text('{}')
            env=dict(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_EVENT_PATH=str(p/'event'),
                GITHUB_SHA=B,GITHUB_REPOSITORY='owner/repo', TARGET_BRANCH='feat/p4-vente-caisse',
                EXPECTED_SHA=A,GITHUB_OUTPUT=str(p/'out'),GITHUB_STEP_SUMMARY=str(p/'summary'))
            with patch.dict(os.environ,env),patch('policy.subprocess.check_output',return_value=B.encode()):
                policy.main()
            output=(p/'out').read_text()
            self.assertIn('sha='+A,output); self.assertIn('control_sha='+B,output)
            self.assertIn('full=true',output)


class RequiredP45(unittest.TestCase):
    def make(self, root):
        for pair in browser.JOURNEYS[:9]:
            for name in pair:
                if name:
                    p=root/'tests'/name; p.parent.mkdir(exist_ok=True); p.touch()
        marker=root/'src/neosys_pharma/application/regularisation_service.py'
        marker.parent.mkdir(parents=True); marker.touch()

    def test_all_nine_journeys_are_scheduled_on_p45(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.make(root)
            names=[c[-1] for c in browser.commands(root)]
            for _,journey in browser.JOURNEYS[:9]: self.assertIn('tests/'+journey,names)

    def test_each_missing_known_p45_journey_is_rejected(self):
        for _,journey in browser.JOURNEYS[:9]:
            with self.subTest(journey=journey), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); self.make(root); (root/'tests'/journey).unlink()
                with self.assertRaisesRegex(ValueError,'obligatoires absents'): browser.commands(root)

    def test_migration_still_requires_p45_if_service_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.make(root)
            (root/'src/neosys_pharma/application/regularisation_service.py').unlink()
            (root/'migrations/versions').mkdir(parents=True)
            (root/'migrations/versions/f22f6abb13c5_p4.py').touch()
            (root/'tests/browser_regularisation.py').unlink()
            with self.assertRaisesRegex(ValueError,'obligatoires absents'): browser.commands(root)

    def test_each_seed_required_by_the_p45_chain_is_rejected_if_missing(self):
        for seed,_ in browser.JOURNEYS[:9]:
            if not seed: continue
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); self.make(root); (root/'tests'/seed).unlink()
                with self.assertRaisesRegex(ValueError,'données absent'): browser.commands(root)


class RequiredP4B(unittest.TestCase):
    def make(self, root):
        for pair in browser.JOURNEYS:
            for name in pair:
                if name:
                    path = root / 'tests' / name
                    path.parent.mkdir(exist_ok=True)
                    path.touch()
        (root / 'src/neosys_pharma/application/regularisation_service.py').parent.mkdir(parents=True, exist_ok=True)
        (root / 'src/neosys_pharma/application/regularisation_service.py').touch()
        (root / 'migrations/versions').mkdir(parents=True, exist_ok=True)
        (root / 'migrations/versions/20261015_01_p4b.py').touch()

    def test_p4b_chromium_journey_and_seed_are_scheduled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make(root)
            commands = [command[-1] for command in browser.commands(root)]
            self.assertEqual(commands[-2:], ['tests/seed_browser_clients.py', 'tests/browser_clients.py'])

    def test_p4b_journey_and_seed_are_required(self):
        for name in ('browser_clients.py', 'seed_browser_clients.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make(root)
                (root / 'tests' / name).unlink()
                with self.assertRaisesRegex(ValueError, 'obligatoires absents|données absent'):
                    browser.commands(root)


if __name__=='__main__': unittest.main()
