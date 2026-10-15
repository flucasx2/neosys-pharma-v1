import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ci'))
from policy import classify, documentation, changed_paths, plan, verdict, main
import browser
import receipt

A, B = 'a' * 40, 'b' * 40
GOOD = dict(sqlite='success', postgres='success', browser='success')


class Policy(unittest.TestCase):
    def test_document_allowlist(self):
        for p in ['README.md', 'docs/P4.md', 'docs/nested/recette.rst', 'docs/notes.txt']:
            self.assertTrue(documentation(p), p)
        for p in ['src/README.md', 'docs/run.py', 'docs/schema.sql', '.github/workflows/tests.yml',
                  'tests/test_auth.py', 'pyproject.toml', 'migrations/a.py', 'docs/../src/x.md']:
            self.assertFalse(documentation(p), p)

    def test_empty_diff_is_conservative(self):
        self.assertTrue(classify([]))

    def test_mixed_changes(self):
        self.assertTrue(classify(['docs/P4.md', 'src/app.py']))

    def test_draft_only_sqlite(self):
        p = plan('pull_request', {'pull_request': {'draft': True}}, A, ['src/app.py'])
        self.assertTrue(p['sqlite']); self.assertFalse(p['full'])

    def test_doc_draft_and_ready_light(self):
        for draft in [True, False]:
            p = plan('pull_request', {'pull_request': {'draft': draft}}, A, ['docs/P4.md'])
            self.assertFalse(p['sqlite']); self.assertFalse(p['full'])

    def test_ready_and_reopened_code_full(self):
        for action in ['opened', 'ready_for_review', 'reopened', 'synchronize']:
            p = plan('pull_request', {'action': action, 'pull_request': {'draft': False}}, A, ['tests/x.py'])
            self.assertTrue(p['full']); self.assertTrue(p['sqlite'])

    def test_missing_draft_defaults_to_draft(self):
        self.assertFalse(plan('pull_request', {}, A, ['src/x.py'])['full'])

    def test_manual_forces_full_even_docs(self):
        p = plan('workflow_dispatch', {}, A, ['docs/P4.md'])
        self.assertTrue(p['full']); self.assertTrue(p['sqlite'])

    def test_push_main_sqlite(self):
        self.assertTrue(plan('push', {}, A, ['src/x.py'])['sqlite'])
        self.assertFalse(plan('push', {}, A, ['src/x.py'])['full'])

    def test_bad_sha_and_event_rejected(self):
        for event, sha in [('pull_request', 'main'), ('other', A)]:
            with self.assertRaises(ValueError): plan(event, {}, sha, [])

    def test_skipped_never_means_complete(self):
        for job in GOOD:
            for result in ['skipped', 'failure', 'cancelled', '', 'pending']:
                self.assertEqual(verdict(True, dict(GOOD, **{job: result}), A, A, A)[0], 'failure')

    def test_missing_job_rejected(self):
        self.assertEqual(verdict(True, {'sqlite': 'success'}, A, A, A)[0], 'failure')

    def test_complete_exact_commit(self):
        self.assertEqual(verdict(True, GOOD, A, A, A)[0], 'success')

    def test_new_head_invalidates_recipe(self):
        self.assertEqual(verdict(True, GOOD, A, B, A)[0], 'failure')

    def test_wrong_checkout_rejected(self):
        self.assertEqual(verdict(True, GOOD, A, A, B)[0], 'failure')

    def test_docs_and_draft_are_pending_not_final_success(self):
        self.assertEqual(verdict(False, GOOD, A, A, A)[0], 'pending')

    def test_real_git_diff_rename_delete_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                return subprocess.check_output(['git', '-C', tmp, *args]).decode().strip()
            git('init', '-q'); git('config', 'user.name', 'CI'); git('config', 'user.email', 'ci@example.invalid')
            p = Path(tmp); (p / 'app.py').write_text('x = 1\n'); (p / 'docs').mkdir()
            (p / 'docs/État.md').write_text('avant\n')
            git('add', '.'); git('commit', '-qm', 'before'); before = git('rev-parse', 'HEAD')
            (p / 'app.py').rename(p / 'docs/app.md'); (p / 'docs/État.md').unlink()
            git('add', '-A'); git('commit', '-qm', 'after'); after = git('rev-parse', 'HEAD')
            old = os.getcwd(); os.chdir(tmp)
            try: paths = changed_paths(before, after)
            finally: os.chdir(old)
            self.assertEqual(set(paths), {'app.py', 'docs/app.md', 'docs/État.md'})
            self.assertTrue(classify(paths))

    def test_sync_doc_delta_does_not_retest_prior_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); event = p / 'event.json'; out = p / 'out'; summary = p / 'summary'
            event.write_text(json.dumps({'action': 'synchronize', 'before': B,
                'pull_request': {'draft': True, 'head': {'sha': A}, 'base': {'sha': 'c' * 40}}}))
            env = dict(GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(event),
                       GITHUB_OUTPUT=str(out), GITHUB_STEP_SUMMARY=str(summary))
            with patch.dict(os.environ, env), patch('policy.changed_paths', return_value=['docs/P4.md']) as diff:
                main()
            diff.assert_called_once_with(B, A)
            self.assertIn('full=false', out.read_text()); self.assertIn('sqlite=false', out.read_text())

    def test_force_push_unavailable_diff_falls_back_to_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); event = p / 'event.json'
            event.write_text(json.dumps({'action': 'synchronize', 'before': B,
                'pull_request': {'draft': True, 'head': {'sha': A}, 'base': {'sha': 'c' * 40}}}))
            env = dict(GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(event),
                       GITHUB_OUTPUT=str(p / 'out'), GITHUB_STEP_SUMMARY=str(p / 'summary'))
            with patch.dict(os.environ, env), patch('policy.changed_paths', side_effect=ValueError('unreachable')) as diff:
                main()
            self.assertEqual(diff.call_count, 2)
            self.assertIn('sqlite=true', (p / 'out').read_text())
            self.assertIn('full=false', (p / 'out').read_text())

    def test_ready_reopened_compare_whole_pr(self):
        for action in ['ready_for_review', 'reopened']:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp); event = p / 'event.json'
                event.write_text(json.dumps({'action': action, 'before': B,
                    'pull_request': {'draft': False, 'head': {'sha': A}, 'base': {'sha': 'c' * 40}}}))
                env = dict(GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(event),
                           GITHUB_OUTPUT=str(p / 'out'), GITHUB_STEP_SUMMARY=str(p / 'summary'))
                with patch.dict(os.environ, env), patch('policy.changed_paths', return_value=['src/app.py']) as diff:
                    main()
                diff.assert_called_once_with('c' * 40, A)
                self.assertIn('full=true', (p / 'out').read_text())


class Receipt(unittest.TestCase):
    def test_start_revokes_previous_success_on_exact_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'event'; f.write_text('{}')
            with patch.dict(os.environ, dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_EVENT_PATH=str(f),
                    GITHUB_REPOSITORY='owner/repo', TESTED_SHA=A)), patch.object(sys, 'argv', ['receipt.py', 'start']), \
                    patch('receipt.status') as post:
                receipt.main()
            post.assert_called_once_with('owner/repo', A, 'pending', 'Validation complète de ce commit en attente')

    def test_manual_looks_up_branch_current_head(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main', 'TARGET_BRANCH': 'feat/p4-vente-caisse'}), \
                patch('receipt.api', return_value={'object': {'sha': B}}) as get:
            self.assertEqual(receipt.current_head('workflow_dispatch', {}, 'owner/repo'), B)
            get.assert_called_once_with('/repos/owner/repo/git/ref/heads/feat/p4-vente-caisse')

    def test_auto_looks_up_live_pr_head(self):
        with patch('receipt.api', return_value={'head': {'sha': B}}) as get:
            self.assertEqual(receipt.current_head('pull_request', {'number': 4}, 'owner/repo'), B)
            get.assert_called_once_with('/repos/owner/repo/pulls/4')

    def test_finish_api_failure_revokes_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'event'; f.write_text('{}')
            env = dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_EVENT_PATH=str(f),
                       GITHUB_REPOSITORY='owner/repo', TESTED_SHA=A, ACTUAL_SHA=A,
                       JOB_RESULTS=json.dumps(GOOD), FULL='true')
            with patch.dict(os.environ, env), patch.object(sys, 'argv', ['receipt.py', 'finish']), \
                    patch('receipt.current_head', side_effect=OSError('API unavailable')), patch('receipt.status') as post:
                with self.assertRaises(OSError): receipt.main()
            post.assert_called_once_with('owner/repo', A, 'failure', 'Impossible de vérifier le commit courant')

    def test_finish_full_and_light_publish_different_statuses(self):
        for full, expected in [('true', 'success'), ('false', 'pending')]:
            with tempfile.TemporaryDirectory() as tmp:
                f = Path(tmp) / 'event'; f.write_text('{}')
                env = dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_EVENT_PATH=str(f),
                           GITHUB_REPOSITORY='owner/repo', TESTED_SHA=A, ACTUAL_SHA=A,
                           JOB_RESULTS=json.dumps(GOOD), FULL=full, GITHUB_STEP_SUMMARY=str(Path(tmp) / 'summary'))
                with patch.dict(os.environ, env), patch.object(sys, 'argv', ['receipt.py', 'finish']), \
                        patch('receipt.current_head', return_value=A), patch('receipt.status') as post:
                    receipt.main()
                self.assertEqual(post.call_args.args[:3], ('owner/repo', A, expected))

    def test_fork_cannot_claim_final_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'event'
            f.write_text(json.dumps({'pull_request': {'head': {'repo': {'full_name': 'external/repo'}}}}))
            env = dict(GITHUB_EVENT_NAME='pull_request', GITHUB_EVENT_PATH=str(f),
                       GITHUB_REPOSITORY='owner/repo', TESTED_SHA=A)
            with patch.dict(os.environ, env), patch.object(sys, 'argv', ['receipt.py', 'start']), patch('receipt.status') as post:
                with self.assertRaises(ValueError): receipt.main()
                post.assert_not_called()

    def test_tag_recipe_rejected(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/tags/v1'}):
            with self.assertRaises(ValueError): receipt.current_head('push', {}, 'owner/repo')


class Browser(unittest.TestCase):
    def test_current_journeys_preserved(self):
        names = [c[-1] for c in browser.commands(ROOT)]
        self.assertIn('tests/browser_p1.py', names)
        self.assertIn('tests/browser_etats_p3.py', names)
        self.assertLess(names.index('tests/seed_browser_p2.py'), names.index('tests/browser_p2.py'))

    def test_future_p45_journey_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p / 'tests').mkdir()
            for name in {n for pair in browser.JOURNEYS for n in pair if n}:
                (p / 'tests' / name).touch()
            names = [c[-1] for c in browser.commands(p)]
            self.assertLess(names.index('tests/seed_browser_regularisation.py'), names.index('tests/browser_regularisation.py'))
            self.assertEqual(names[-2:], ['tests/seed_browser_clients.py', 'tests/browser_clients.py'])

    def test_unknown_or_missing_seed_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p / 'tests').mkdir(); (p / 'tests/browser_future.py').touch()
            with self.assertRaises(ValueError): browser.commands(p)
            (p / 'tests/browser_future.py').unlink(); (p / 'tests/browser_p1.py').touch()
            with self.assertRaises(ValueError): browser.commands(p)


if __name__ == '__main__':
    unittest.main()
