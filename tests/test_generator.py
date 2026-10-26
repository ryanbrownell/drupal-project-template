"""Integration tests use disposable directories and never contact real services."""

import ast
import importlib.util
import json
import os
from pathlib import Path
import pty
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/create_project.py"

FAKE_LANDO = r'''
import json, os, pathlib, shutil, sys
root = pathlib.Path.cwd()
arguments = sys.argv[1:]
with open(os.environ['TOOL_LOG'], 'a') as log:
    log.write(json.dumps(arguments) + '\n')
failure = os.environ.get('FAIL_LANDO', '')
marker = pathlib.Path(os.environ['TOOL_LOG'] + '.failed')
if failure and arguments[:len(failure.split())] == failure.split() and not marker.exists():
    marker.touch()
    sys.exit(42)
if arguments == ['start']:
    assert (root / 'dev.local.env').is_file()
elif arguments[:2] == ['composer', 'create-project']:
    target = root / arguments[-1]
    target.mkdir()
    upstream = {
        'name': 'drupal/recommended-project', 'type': 'project',
        'require': {
            'composer/installers': '^2.3',
            'drupal/core-recommended': '^11.99.0',
            'drupal/core-composer-scaffold': '^11.99.0',
            'drupal/core-project-message': '^11.99.0'
        },
        'config': {'allow-plugins': {'drupal/core-project-message': True}},
        'extra': {'upstream-metadata': {'preserved': True}},
    }
    (target / 'composer.json').write_text(json.dumps(upstream))
    (target / 'README.md').write_text('Upstream README must not replace project documentation.')
    (target / 'LICENSE.txt').write_text('Fixture license')
elif arguments[:2] == ['composer', 'install']:
    manifest = json.loads((root / 'composer.json').read_text())
    assert manifest['require']['drupal/core-recommended'] != '*'
    (root / 'composer.lock').write_text(json.dumps({'packages': [], 'packages-dev': []}))
    (root / 'vendor').mkdir(exist_ok=True)
    (root / 'vendor/autoload.php').touch()
    path = root / 'web/sites/default'
    path.mkdir(parents=True, exist_ok=True)
    (path / 'default.settings.php').write_text('<?php\n')
elif arguments[:2] == ['composer', 'patches-relock']:
    (root / 'patches.lock.json').write_text(json.dumps({'patches': {}}))
elif arguments[:2] == ['composer', 'validate']:
    assert (root / 'composer.lock').is_file()
elif arguments == ['php', 'scripts/prepare-settings.php', 'local']:
    pass
elif arguments == ['install']:
    pass
elif arguments and arguments[0] == 'drush':
    pass
else:
    raise AssertionError('Unexpected Lando command: ' + repr(arguments))
'''


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="drupal-generator-test-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.target = self.work / "site with spaces"
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.log = self.work / "tools.jsonl"
        self.env = dict(os.environ, TOOL_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]

    def executable(self, name, content):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(content))
        path.chmod(0o755)
        return path

    def generate(self, *extra, scaffold=True, git=False, check=True, destination=None):
        command = [sys.executable, str(GENERATOR), str(destination or self.target), "--yes"]
        if scaffold:
            command.append("--scaffold-only")
        if not git:
            command.append("--no-git")
        result = subprocess.run(command + list(extra), cwd=self.work, env=self.env, text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []


class RenderingTests(WorkspaceTest):
    def test_expected_tooling_and_empty_configuration(self):
        self.generate()
        paths = [
            ".lando.yml", ".lando/php/php.ini", ".lando/drupal/settings.local.php",
            ".lando/drupal/secrets.php", ".lando/drupal/secrets.local.php",
            ".lando/drush/drush.yml", ".github/drupal/settings.local.php",
            ".github/workflows/quality.yml", ".github/workflows/deploy.yml",
            ".github/workflows/dev_deploy.yml", ".github/workflows/test_deploy.yml",
            ".github/workflows/prod_deploy.yml", "composer.json", "patches.json",
            "patches/README.md", "README.md", "AGENTS.md", "TODO.md", "dev.local.env",
            "scripts/setup.sh", "scripts/setup-project.py", "scripts/install-site.php",
            "scripts/launch-testing-release.sh", "phpcs.xml.dist", "phpstan.neon.dist",
            "phpunit.xml.dist", "templates/server.settings.local.php",
        ]
        for name in paths:
            self.assertTrue((self.target / name).is_file(), name)
        for environment in ("default", "local", "dev", "test", "prod"):
            self.assertEqual([file.name for file in (self.target / "config" / environment).iterdir()], [".gitkeep"])
        for forbidden in ("vendor", "web/core", "secrets.php", "secrets.local.php", "composer.lock", "patches.lock.json"):
            self.assertFalse((self.target / forbidden).exists(), forbidden)
        self.assertFalse(self.log.exists(), "Scaffold rendering must not run Lando")

    def test_user_values_are_serialized_without_shell_execution(self):
        sentinel = self.work / "must-not-exist"
        name = 'Élan "Client" \\ ${HOME} $(touch ' + str(sentinel) + ") `touch unwanted`"
        self.generate("--site-name", name, "--machine-name", "client-site", "--url", "HTTPS://Client.LNDO.SITE/", "--timezone", "America/Halifax")
        project = json.loads((self.target / "project.json").read_text())
        self.assertEqual(project["site_name"], name)
        self.assertEqual(project["url"], "https://client.lndo.site")
        self.assertEqual(project["timezone"], "America/Halifax")
        self.assertFalse(sentinel.exists())
        self.assertFalse((self.work / "unwanted").exists())
        self.assertIn("client\\\\.lndo\\\\.site", (self.target / ".lando/drupal/settings.local.php").read_text())

    def test_all_rendered_formats_and_placeholders(self):
        self.generate()
        for path in self.target.rglob("*"):
            if not path.is_file():
                continue
            content = path.read_text()
            self.assertFalse(re.search(r"@@[A-Z_]+@@", content), str(path))
            # Generated files must not depend on this checkout or sibling source projects.
            self.assertNotIn(str(ROOT.parent), content, str(path))
            if path.suffix == ".json":
                json.loads(content)
            if content.startswith("<?xml"):
                ET.fromstring(content)
            if path.suffix == ".py":
                ast.parse(content)
            if path.suffix == ".sh":
                subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True)
                self.assertTrue(os.access(path, os.X_OK), str(path))

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "Optional PyYAML is not installed")
    def test_yaml_and_workflow_contracts(self):
        import yaml
        self.generate("--database-port", "3401", "--php", "8.3")
        documents = {}
        for path in self.target.rglob("*.yml"):
            documents[str(path.relative_to(self.target))] = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        lando = documents[".lando.yml"]
        self.assertEqual(lando["services"]["database"]["portforward"], "3401")
        self.assertEqual(lando["config"]["php"], "8.3")
        self.assertNotIn("build", lando["services"]["appserver"])
        self.assertIn("post-start", lando["events"])
        deploy = documents[".github/workflows/deploy.yml"]
        self.assertIn("workflow_call", deploy["on"])
        self.assertIn("DEPLOY_ENABLED", deploy["jobs"]["quality"]["if"])
        self.assertEqual(deploy["jobs"]["deploy"]["environment"], "${{ inputs.environment }}")
        checkout = deploy["jobs"]["deploy"]["steps"][0]
        self.assertIn("format('refs/tags/{0}', inputs.ref)", checkout["with"]["ref"])
        for environment in ("dev", "test", "prod"):
            job = documents[f".github/workflows/{environment}_deploy.yml"]["jobs"]["deploy"]
            self.assertEqual(job["with"]["environment"], environment)
            self.assertEqual(job["uses"], "./.github/workflows/deploy.yml")

    def test_nonempty_hidden_file_is_preserved(self):
        self.target.mkdir()
        sentinel = self.target / ".existing"
        sentinel.write_text("keep")
        result = self.generate(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completely empty", result.stderr)
        self.assertEqual(list(self.target.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), "keep")

    def test_symlink_destination_is_rejected(self):
        actual = self.work / "actual"
        actual.mkdir()
        self.target.symlink_to(actual, target_is_directory=True)
        self.assertNotEqual(self.generate(check=False).returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])

    def test_file_destination_is_rejected(self):
        self.target.write_text("keep")
        self.assertNotEqual(self.generate(check=False).returncode, 0)
        self.assertEqual(self.target.read_text(), "keep")

    def test_empty_existing_directory_is_supported(self):
        self.target.mkdir()
        self.generate()
        self.assertTrue((self.target / "composer.json").exists())

    def test_invalid_inputs_do_not_create_a_project(self):
        for arguments in (
            ["--machine-name", "Bad_Name"], ["--machine-name", "-invalid"],
            ["--machine-name", "site-"], ["--database-port", "80"],
            ["--database-port", "65536"], ["--url", "https://user:pass@site.test"],
            ["--url", "https://site.test:443"], ["--url", "https://site.test/path"],
            ["--url", "https://site..test"], ["--url", "https://-site.test"],
            ["--url", "https://site.test/?value=x"], ["--url", "ftp://site.test"],
            ["--email", "not-an-email"], ["--site-name", "unsafe\nheading"],
            ["--site-name", "@@SITE_NAME@@"], ["--timezone", "Nowhere/Unknown"],
            ["--drupal-version", "11.x-dev"], ["--locale", "../../fr"],
        ):
            with self.subTest(arguments=arguments):
                self.assertNotEqual(self.generate(*arguments, check=False).returncode, 0)
                self.assertFalse(self.target.exists())

    def test_noninteractive_requires_explicit_defaults(self):
        result = subprocess.run([sys.executable, str(GENERATOR), str(self.target), "--scaffold-only"], input="", text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--yes", result.stderr)
        self.assertFalse(self.target.exists())

    def test_interactive_defaults(self):
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(GENERATOR), str(self.target), "--scaffold-only", "--no-git"], stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, text=True)
            os.write(master, b"\n" * 20)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertIn("Local URL", stdout)
            self.assertEqual(json.loads((self.target / "project.json").read_text())["profile"], "minimal")
        finally:
            os.close(master)
            os.close(slave)

    def test_git_initialization_and_ignore_boundaries(self):
        self.generate(git=True, *["--git-remote", "git@example.invalid:owner/site.git"])
        def git(*args):
            return subprocess.run(["git", "-C", str(self.target), *args], text=True, capture_output=True)
        self.assertEqual(git("branch", "--show-current").stdout.strip(), "main")
        self.assertEqual(git("remote", "get-url", "origin").stdout.strip(), "git@example.invalid:owner/site.git")
        for name in ("secrets.php", "secrets.local.php", "dev.local.env", "vendor/autoload.php", "web/core/core.services.yml", "drush/sites/self.site.yml"):
            self.assertEqual(git("check-ignore", "-q", name).returncode, 0, name)
        for name in (".editorconfig", ".gitattributes", "composer.lock", "patches.lock.json", "web/modules/custom/example/example.info.yml", "drush/Commands/Example.php"):
            self.assertEqual(git("check-ignore", "-q", name).returncode, 1, name)
        self.assertNotEqual(git("rev-parse", "--verify", "HEAD").returncode, 0, "Generation must not create commits")

    def test_missing_lando_fails_before_writing_files(self):
        self.env["PATH"] = str(self.bin)
        result = self.generate(scaffold=False, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Lando is required", result.stderr)
        self.assertFalse(self.target.exists())

    def test_relocated_generator_needs_no_source_project(self):
        relocated = self.work / "portable generator"
        shutil.copytree(ROOT, relocated, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        result = subprocess.run(["bash", str(relocated / "create-project.sh"), str(self.target), "--yes", "--scaffold-only", "--no-git"], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / "scripts/setup-project.py").exists())


class SetupTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.executable("lando", FAKE_LANDO)

    def setup(self, *args, check=True):
        result = subprocess.run([sys.executable, str(self.target / "scripts/setup-project.py"), *args], cwd=self.work, env=self.env, text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_full_setup_uses_lando_and_current_upstream_manifest(self):
        self.generate(scaffold=False)
        commands = self.records()
        self.assertEqual(commands[0], ["start"])
        self.assertEqual(commands[1][:2], ["composer", "create-project"])
        self.assertIn("--no-install", commands[1])
        self.assertIn("drupal/recommended-project", commands[1])
        self.assertIn(["install"], commands)
        self.assertIn(["drush", "user:login"], commands)
        composer = json.loads((self.target / "composer.json").read_text())
        self.assertEqual(composer["require"]["drupal/core-recommended"], "^11.99.0")
        self.assertEqual(composer["require-dev"]["drupal/core-dev"], "^11.99.0")
        self.assertEqual(composer["require"]["cweagans/composer-patches"], "^2.0")
        self.assertEqual(composer["extra"]["upstream-metadata"], {"preserved": True})
        self.assertTrue(composer["scripts"]["lint"])
        self.assertFalse((self.target / ".drupal-bootstrap").exists())
        self.assertIn("single-site Drupal project", (self.target / "README.md").read_text())
        self.assertTrue((self.target / "LICENSE.txt").exists())

    def test_no_install_does_not_run_the_installer_or_login(self):
        self.generate("--no-install", scaffold=False)
        self.assertNotIn(["install"], self.records())
        self.assertFalse(any(command[0] == "drush" for command in self.records()))
        self.assertTrue((self.target / "composer.lock").exists())

    def test_version_constraint_is_applied_to_the_project_download(self):
        self.generate("--drupal-version", "^11", scaffold=False)
        self.assertIn("drupal/recommended-project:^11", self.records()[1])

    def test_dependency_failure_is_resumable_without_redownloading_scaffold(self):
        self.env["FAIL_LANDO"] = "composer install"
        first = self.generate(scaffold=False, check=False)
        self.assertNotEqual(first.returncode, 0)
        self.assertTrue((self.target / "README.md").exists())
        self.assertNotIn(["install"], self.records())
        self.setup()
        self.assertEqual(sum(command[:2] == ["composer", "create-project"] for command in self.records()), 1)
        self.assertIn(["install"], self.records())

    def test_download_failure_is_resumable(self):
        self.env["FAIL_LANDO"] = "composer create-project"
        self.assertNotEqual(self.generate(scaffold=False, check=False).returncode, 0)
        self.setup()
        self.assertTrue((self.target / "composer.lock").exists())

    def test_locked_clone_does_not_download_a_new_drupal_project(self):
        self.generate(scaffold=False)
        (self.target / ".project-setup.json").unlink()
        (self.target / "dev.local.env").unlink()
        self.log.unlink()
        self.setup()
        self.assertTrue((self.target / "dev.local.env").exists())
        self.assertFalse(any(command[:2] == ["composer", "create-project"] for command in self.records()))
        self.assertFalse(any(command[:2] == ["composer", "patches-relock"] for command in self.records()))

    def test_unrecognized_bootstrap_directory_is_preserved(self):
        self.generate()
        bootstrap = self.target / ".drupal-bootstrap"
        bootstrap.mkdir()
        sentinel = bootstrap / "keep"
        sentinel.write_text("user data")
        result = self.setup(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized", result.stderr)
        self.assertEqual(sentinel.read_text(), "user data")

    def test_bootstrap_symlink_is_preserved(self):
        self.generate()
        outside = self.work / "outside"
        outside.mkdir()
        (self.target / ".drupal-bootstrap").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.setup(check=False).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
