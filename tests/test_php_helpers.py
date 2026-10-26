"""Optional native PHP tests use synthetic settings/DB/Drush fixtures only."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from test_generator import WorkspaceTest

PHP = os.environ.get("DRUPAL_TEMPLATE_TEST_PHP") or shutil.which("php")


@unittest.skipUnless(PHP, "Set DRUPAL_TEMPLATE_TEST_PHP or run with PHP available for helper runtime tests")
class PhpHelperTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.generate("--url", "https://client.lndo.site", "--site-name", "Client's Site")
        self.site = self.target / "web/sites/default"
        self.site.mkdir(parents=True)
        (self.site / "default.settings.php").write_text("<?php\n// Synthetic Drupal settings fixture.\n")
        self.env["LANDO_INFO"] = json.dumps({"database": {
            "creds": {"database": "fixture", "user": "fixture_user", "password": "fixture_password"},
            "internal_connection": {"host": "database", "port": 3306},
        }})
        self.env["PHP_TOOL_LOG"] = str(self.log)

    def php(self, script, *arguments):
        return subprocess.run([str(PHP), "-n", str(self.target / script), *arguments], cwd=self.target, env=self.env, text=True, capture_output=True)

    def harness(self, content):
        path = self.target / "harness.php"
        path.write_text("<?php\n" + content)
        return self.php("harness.php")

    def test_local_settings_are_idempotent_and_salt_is_private(self):
        result = self.php("scripts/prepare-settings.php", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        settings = (self.site / "settings.php").read_text()
        secrets = self.target / "secrets.local.php"
        original = secrets.read_text()
        self.assertIn("hash_salt", original)
        self.assertEqual(secrets.stat().st_mode & 0o077, 0)
        overrides = self.target / "secrets.php"
        self.assertTrue(overrides.is_file())
        self.assertEqual(overrides.stat().st_mode & 0o077, 0)
        overrides.write_text("<?php\n$settings['integration_token'] = 'fixture-token';\n")
        original_overrides = overrides.read_text()
        (self.site / "settings.local.php").write_text("<?php\n// Keep local changes.\n")
        self.php("scripts/prepare-settings.php", "local")
        self.assertEqual(secrets.read_text(), original)
        self.assertEqual(overrides.read_text(), original_overrides)
        self.assertEqual((self.site / "settings.php").read_text(), settings)
        self.assertEqual(settings.count("// Project settings loader."), 1)
        self.assertIn("Keep local changes", (self.site / "settings.local.php").read_text())

    def test_generated_settings_php_loads_local_settings_and_both_secrets_files(self):
        result = self.php("scripts/prepare-settings.php", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with (self.target / "secrets.local.php").open("a") as file:
            file.write("$settings['local_secret_loaded'] = TRUE;\n")
        with (self.target / "secrets.php").open("a") as file:
            file.write("$settings['integration_token'] = 'fixture-token';\n")
        result = self.harness("""
            $app_root = __DIR__ . '/web';
            $settings = $databases = $config = [];
            require __DIR__ . '/web/sites/default/settings.php';
            echo json_encode(['settings' => $settings, 'databases' => $databases]);
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['databases']['default']['default']['database'], 'fixture')
        self.assertTrue(data['settings']['hash_salt'])
        self.assertTrue(data['settings']['local_secret_loaded'])
        self.assertEqual(data['settings']['integration_token'], 'fixture-token')

    def test_local_loader_uses_lando_credentials_and_private_override_order(self):
        self.php("scripts/prepare-settings.php", "local")
        with (self.target / "secrets.local.php").open("a") as file:
            file.write("$settings['fixture'] = 'legacy';\n")
        (self.target / "secrets.php").write_text("<?php\n$settings['fixture'] = 'canonical';\n")
        result = self.harness("""
            $app_root = __DIR__ . '/web';
            $settings = $databases = $config = [];
            require __DIR__ . '/.lando/drupal/settings.local.php';
            echo json_encode(['settings' => $settings, 'databases' => $databases]);
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["settings"]["fixture"], "canonical")
        self.assertEqual(data["settings"]["config_sync_directory"], str(self.target / "config/default"))
        self.assertEqual(data["databases"]["default"]["default"]["password"], "fixture_password")
        self.assertEqual(data["databases"]["default"]["default"]["namespace"], "Drupal\\mysql\\Driver\\Database\\mysql")
        self.assertTrue(data["settings"]["hash_salt"])

    def test_server_loader_resolves_shared_settings_through_live_symlink(self):
        hosting = self.target / "hosting"
        web = hosting / "releases/release-one/web"
        web.mkdir(parents=True)
        shared = hosting / "shared"
        shared.mkdir()
        (hosting / "live").symlink_to(web.parent, target_is_directory=True)
        (shared / "settings.local.php").write_text("<?php\n$settings['fixture'] = 'server';\n")
        (shared / "secrets.local.php").write_text("<?php\n$settings['legacy_loaded'] = TRUE;\n$settings['fixture'] = 'legacy';\n")
        (shared / "secrets.php").write_text("<?php\n$settings['fixture'] = 'canonical';\n")
        result = self.harness("""
            $app_root = __DIR__ . '/hosting/live/web';
            $settings = [];
            require __DIR__ . '/.github/drupal/settings.local.php';
            echo json_encode($settings);
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertEqual(settings["fixture"], "canonical")
        self.assertTrue(settings["legacy_loaded"])
        self.assertEqual(settings["file_private_path"], str(shared / "private"))
        self.assertEqual(settings["config_sync_directory"], str(web.parent / "config/default"))

    def test_deployment_preparation_does_not_create_local_secrets(self):
        result = self.php("scripts/prepare-settings.php", "deploy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / "secrets.local.php").exists())
        self.assertFalse((self.target / "secrets.php").exists())
        self.assertEqual((self.site / "settings.local.php").read_text(), (self.target / ".github/drupal/settings.local.php").read_text())
        self.assertFalse((self.target / "private").exists())

    def test_non_lando_composer_hook_is_a_no_op(self):
        self.env.pop("LANDO_INFO")
        result = self.php("scripts/prepare-settings.php", "auto")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.site / "settings.php").exists())
        self.assertFalse((self.target / "secrets.local.php").exists())
        self.assertFalse((self.target / "secrets.php").exists())

    def tool(self, name):
        path = self.target / "vendor/bin" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("""<?php
            file_put_contents(getenv('PHP_TOOL_LOG'), json_encode(array_slice($argv, 1)) . "\\n", FILE_APPEND);
            exit((int) (getenv('PHP_TOOL_EXIT') ?: 0));
        """)

    def test_nested_root_unit_tests_are_discovered(self):
        test = self.target / "tests/src/Unit/Feature/NestedTest.php"
        test.parent.mkdir()
        test.write_text("<?php\n")
        self.tool("phpunit")
        result = self.php("scripts/quality.php", "test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unit", self.records()[0])

    def test_empty_custom_code_and_unit_suites_are_reported(self):
        for mode in ("lint", "phpstan", "test"):
            result = self.php("scripts/quality.php", mode)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("No ", result.stdout)

    def test_kernel_tests_require_an_explicit_test_database(self):
        (self.target / "tests/src/Kernel/ExampleTest.php").write_text("<?php\n")
        self.env.pop("SIMPLETEST_DB", None)
        self.tool("phpunit")
        result = self.php("scripts/quality.php", "test:kernel")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("isolated test database", result.stderr)
        self.assertFalse(self.log.exists())

    def test_quality_tool_failure_is_propagated(self):
        module = self.target / "web/modules/custom/example"
        module.mkdir()
        (module / "example.module").write_text("<?php\n")
        self.tool("phpstan")
        self.env["PHP_TOOL_EXIT"] = "42"
        result = self.php("scripts/quality.php", "phpstan")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)

    def installer_fixture(self):
        vendor = self.target / "vendor"
        vendor.mkdir(exist_ok=True)
        (vendor / "autoload.php").write_text("<?php\n")
        drush = vendor / "bin/drush"
        drush.parent.mkdir(exist_ok=True)
        drush.write_text("""<?php
            $arguments = array_slice($argv, 1);
            file_put_contents(getenv('PHP_TOOL_LOG'), json_encode($arguments) . "\\n", FILE_APPEND);
            if (getenv('PHP_DRUSH_FAIL') === ($arguments[2] ?? '')) {
                exit(42);
            }
            if (($arguments[2] ?? '') === 'sql:query' && getenv('PHP_DB_TABLES')) {
                echo 'existing_table';
            }
            if (($arguments[2] ?? '') === 'status') {
                echo getenv('PHP_BOOTSTRAP') ?: 'Successful';
            }
        """)

    def test_installer_handles_empty_database_and_passes_literal_user_values(self):
        self.installer_fixture()
        self.env.pop("PHP_DB_TABLES", None)
        result = self.php("scripts/install-site.php")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self.records()
        self.assertEqual(commands[0][2], "sql:query")
        self.assertEqual(commands[1][2], "site:install")
        self.assertIn("--site-name=Client's Site", commands[1])
        self.assertIn("--account-name=admin", commands[1])
        self.assertEqual(commands[2][2], "config:set")

    def test_installer_preserves_existing_drupal(self):
        self.installer_fixture()
        self.env["PHP_DB_TABLES"] = "1"
        result = self.php("scripts/install-site.php")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.records()), 2)
        self.assertIn("preserved", result.stdout)

    def test_installer_refuses_nonempty_database_with_failed_bootstrap(self):
        self.installer_fixture()
        self.env.update(PHP_DB_TABLES="1", PHP_BOOTSTRAP="Failed")
        result = self.php("scripts/install-site.php")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to reinstall", result.stderr)
        self.assertEqual(len(self.records()), 2)

    def test_installer_query_failure_is_not_treated_as_an_empty_database(self):
        self.installer_fixture()
        self.env['PHP_DRUSH_FAIL'] = 'sql:query'
        result = self.php('scripts/install-site.php')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.records()), 1)
        self.assertNotIn('site:install', self.records()[0])
