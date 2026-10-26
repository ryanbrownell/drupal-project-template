"""Exercise release Git behavior and deployment shell orchestration locally."""

import json
import os
from pathlib import Path
import subprocess
import textwrap

from test_generator import WorkspaceTest


class ReleaseTests(WorkspaceTest):
    def test_bundled_release_regressions(self):
        self.generate()
        result = subprocess.run(["bash", str(self.target / "scripts/tests/launch-testing-release.test.sh")], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.target), *arguments], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def repository(self, previous_release=True):
        self.generate(git=True)
        self.git("config", "user.name", "Template Test")
        self.git("config", "user.email", "template@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "Initial project")
        if previous_release:
            self.git("tag", "v1.0.0")
        self.git("checkout", "-b", "codex")
        (self.target / "feature.txt").write_text("Feature to release\n")
        self.git("add", "feature.txt")
        self.git("commit", "-m", "Add a feature")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "codex", "-m", "Merge feature")
        self.origin = self.work / "origin.git"
        subprocess.run(["git", "init", "--bare", str(self.origin)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "origin", "main", "codex", "--tags")
        self.executable("codex", r'''
            import os, pathlib, subprocess, sys
            assert '--ignore-user-config' in sys.argv
            policy = pathlib.Path('AGENTS.md').read_text().split('## Release Notes Requests\n', 1)[1].split('\n## ', 1)[0].rstrip('\n')
            assert sys.argv[-1].endswith('## Release Notes Requests\n' + policy)
            if os.environ.get('RELEASE_GENERATION_FAIL'):
                sys.exit(42)
            commit = 'HEAD^' if os.environ.get('RELEASE_STALE_TAG') else 'HEAD'
            subprocess.run(['git', 'tag', 'v1.1.0', commit], check=True)
            subprocess.run(['git', 'push', 'origin', 'v1.1.0'], check=True, capture_output=True)
            if os.environ.get('RELEASE_REMOTE_MOVED'):
                head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
                origin = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip()
                subprocess.run(['git', '--git-dir=' + origin, 'update-ref', 'refs/heads/codex', head], check=True)
        ''')

    def launch(self):
        return subprocess.run(["bash", str(self.target / "scripts/launch-testing-release.sh")], cwd=self.target, input="done\n", env=self.env, text=True, capture_output=True)

    def test_real_git_release_fast_forwards_without_rewriting_work(self):
        self.repository()
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "codex")
        self.assertEqual(self.git("rev-parse", "codex"), self.git("rev-parse", "origin/main"))
        self.assertEqual(self.git("rev-parse", "codex"), self.git("rev-parse", "origin/codex"))
        self.assertEqual(self.git("rev-parse", "v1.1.0"), self.git("rev-parse", "HEAD"))

    def test_real_git_first_release(self):
        self.repository(previous_release=False)
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("first stable release", result.stdout)
        self.assertEqual(self.git("rev-parse", "codex"), self.git("rev-parse", "main"))

    def test_stale_tag_does_not_advance_codex(self):
        self.repository()
        previous = self.git("rev-parse", "codex")
        self.env["RELEASE_STALE_TAG"] = "1"
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("do not all identify the same commit", result.stderr)
        self.assertEqual(self.git("rev-parse", "codex"), previous)
        self.assertEqual(self.git("rev-parse", "origin/codex"), previous)

    def test_remote_branch_race_is_rejected(self):
        self.repository()
        previous = self.git("rev-parse", "codex")
        self.env["RELEASE_REMOTE_MOVED"] = "1"
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed during release preparation", result.stderr)
        self.assertEqual(self.git("rev-parse", "codex"), previous)

    def test_note_generation_failure_preserves_codex(self):
        self.repository()
        previous = self.git("rev-parse", "codex")
        self.env["RELEASE_GENERATION_FAIL"] = "1"
        result = self.launch()
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertEqual(self.git("rev-parse", "codex"), previous)


class UploadTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.generate()
        (self.target / "config/default/core.extension.yml").write_text("module: {}\n")
        (self.target / "composer.lock").write_text("{}\n")
        (self.target / "vendor").mkdir()
        (self.target / "vendor/autoload.php").touch()
        (self.target / "web/sites/default").mkdir(parents=True)
        (self.target / "web/sites/default/settings.local.php").touch()
        self.env.update(SSH_HOST="deploy.example.invalid", SSH_USER="deploy", DEPLOY_ROOT="/srv/www/example", SITE_URI="https://site.example.invalid")
        self.executable("git", "import sys\nassert sys.argv[1] == 'rev-parse'\nprint('abc123abc123')\n")
        for name in ("ssh", "rsync"):
            self.executable(name, '''
                import json, os, pathlib, sys
                name = pathlib.Path(sys.argv[0]).name
                with open(os.environ['TOOL_LOG'], 'a') as log:
                    log.write(json.dumps([name] + sys.argv[1:]) + '\\n')
                if os.environ.get('FAIL_UPLOAD') == name:
                    sys.exit(42)
                if name == 'ssh' and 'bash' in sys.argv:
                    assert 'set -Eeuo pipefail' in sys.stdin.read()
            ''')

    def deploy(self):
        return subprocess.run(["bash", str(self.target / "scripts/deploy.sh")], cwd=self.target, env=self.env, text=True, capture_output=True)

    def test_upload_uses_verified_hosts_and_shared_exclusions(self):
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        records = self.records()
        self.assertEqual([record[0] for record in records], ["ssh", "rsync", "ssh"])
        self.assertIn("StrictHostKeyChecking=yes", records[0])
        self.assertIn("--exclude-from=.github/deploy-excludes", records[1])
        exclusions = (self.target / ".github/deploy-excludes").read_text()
        for path in ("/secrets.php", "/secrets.local.php", "/private/", "/web/sites/default/files/", "/dev.local.env", "/.git/"):
            self.assertIn(path + "\n", exclusions)

    def test_invalid_target_never_reaches_ssh(self):
        for key, value in (
            ("DEPLOY_ROOT", "/"), ("DEPLOY_ROOT", "/srv/site/../other"),
            ("DEPLOY_ROOT", "/srv/site/.."), ("DEPLOY_ROOT", "/srv/./site"),
            ("DEPLOY_ROOT", "/srv/site;touch /tmp/pwned"), ("SSH_HOST", "-option"),
            ("SSH_HOST", "example.invalid;false"), ("SSH_PORT", "65536"),
            ("SITE_URI", "https://example.invalid/;false"), ("INITIAL_INSTALL", "yes"),
        ):
            with self.subTest(key=key, value=value):
                old = self.env.get(key)
                self.env[key] = value
                self.assertNotEqual(self.deploy().returncode, 0)
                self.assertFalse(self.log.exists())
                if old is None:
                    self.env.pop(key)
                else:
                    self.env[key] = old

    def test_domain_named_hosting_directories_are_supported(self):
        self.env['DEPLOY_ROOT'] = '/home/deploy/web/dev.example.com/public_html'
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('/home/deploy/web/dev.example.com/public_html/releases/', self.records()[0][-1])

    def test_missing_configuration_stops_before_network(self):
        (self.target / "config/default/core.extension.yml").unlink()
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Export and commit", result.stderr)
        self.assertFalse(self.log.exists())

    def test_upload_failure_does_not_run_remote_migrations(self):
        self.env["FAIL_UPLOAD"] = "rsync"
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertEqual([record[0] for record in self.records()], ["ssh", "rsync"])


class RemoteDeploymentTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.generate()
        self.hosting = self.work / "hosting"
        self.release = self.hosting / "releases/new-release"
        for directory in (self.release / "web/sites/default", self.release / "vendor/bin", self.release / "config/default", self.hosting / "shared/files", self.hosting / "shared/private"):
            directory.mkdir(parents=True)
        for file in (self.release / "web/index.php", self.release / "vendor/bin/drush", self.release / "config/default/core.extension.yml", self.hosting / "shared/settings.local.php"):
            file.touch()
        self.executable("php", r'''
            import json, os, pathlib, sys
            args = sys.argv[1:]
            with open(os.environ['TOOL_LOG'], 'a') as log:
                log.write(json.dumps(args) + '\n')
            if args[0] == '-r':
                print('random-fixture-password')
                sys.exit(0)
            command = args[3]
            if os.environ.get('FAIL_REMOTE') == command:
                sys.exit(42)
            if command == 'status':
                print('Successful')
            elif command == 'sql:query':
                if os.environ.get('NONEMPTY_DATABASE'):
                    print('existing_table')
            elif command == 'sql:dump':
                destination = next(item.split('=',1)[1] for item in args if item.startswith('--result-file='))
                pathlib.Path(destination).write_text('SQL fixture backup')
        ''')

    def existing_site(self):
        previous = self.hosting / "releases/previous"
        (previous / "web").mkdir(parents=True)
        (previous / "vendor/bin").mkdir(parents=True)
        (previous / "vendor/bin/drush").touch()
        (self.hosting / "live").symlink_to(previous, target_is_directory=True)
        return previous

    def deploy(self, initialize=False):
        return subprocess.run(["bash", str(self.target / "scripts/deploy-remote.sh"), str(self.hosting), "https://site.example.invalid", "new-release", str(initialize).lower()], cwd=self.work, env=self.env, text=True, capture_output=True)

    def commands(self):
        return [record[3] for record in self.records() if record[0] != "-r"]

    def test_existing_site_requires_backup_before_migrations_and_activation(self):
        self.existing_site()
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.hosting / "live").resolve(), self.release)
        commands = self.commands()
        self.assertLess(commands.index("sql:dump"), commands.index("deploy"))
        self.assertTrue((self.hosting / "backups/new-release/database.sql.gz").exists())
        self.assertTrue((self.hosting / "backups/new-release/files.tar.gz").exists())
        self.assertEqual((self.release / "web/sites/default/files").resolve(), self.hosting / "shared/files")

    def test_backup_failure_keeps_previous_release_and_skips_migrations(self):
        previous = self.existing_site()
        self.env["FAIL_REMOTE"] = "sql:dump"
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertEqual((self.hosting / "live").resolve(), previous)
        self.assertNotIn("deploy", self.commands())

    def test_migration_failure_does_not_activate_the_new_release(self):
        previous = self.existing_site()
        self.env["FAIL_REMOTE"] = "deploy"
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.hosting / "live").resolve(), previous)
        self.assertIn("maintenance may remain enabled", result.stderr)

    def test_initial_install_requires_explicit_opt_in(self):
        self.assertNotEqual(self.deploy().returncode, 0)
        self.assertNotIn("site:install", self.commands())
        self.assertFalse((self.hosting / "live").exists())

    def test_initial_install_refuses_existing_tables(self):
        self.env["NONEMPTY_DATABASE"] = "1"
        result = self.deploy(initialize=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completely empty database", result.stderr)
        self.assertNotIn("site:install", self.commands())

    def test_initial_install_database_query_failure_is_not_treated_as_empty(self):
        self.env["FAIL_REMOTE"] = "sql:query"
        self.assertNotEqual(self.deploy(initialize=True).returncode, 0)
        self.assertNotIn("site:install", self.commands())

    def test_initial_empty_database_installs_and_activates(self):
        result = self.deploy(initialize=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("site:install", self.commands())
        self.assertEqual((self.hosting / "live").resolve(), self.release)
