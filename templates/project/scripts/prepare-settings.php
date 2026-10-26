<?php

/**
 * @file
 * Prepare generated Drupal settings without rewriting existing credentials.
 */

declare(strict_types=1);

$project_root = dirname(__DIR__);
$mode = $argv[1] ?? 'auto';
if ($mode === 'auto') {
  if (!getenv('LANDO_INFO')) {
    exit(0);
  }
  $mode = 'local';
}
if (!in_array($mode, ['local', 'deploy'], TRUE)) {
  fwrite(STDERR, "Usage: php scripts/prepare-settings.php [auto|local|deploy]\n");
  exit(2);
}

$site_directory = $project_root . '/web/sites/default';
$default_settings = $site_directory . '/default.settings.php';
if (!is_file($default_settings)) {
  fwrite(STDERR, "Drupal is missing. Complete Composer installation first.\n");
  exit(1);
}

$copy_if_missing = static function (string $source, string $destination): void {
  if (!is_file($destination) && !copy($source, $destination)) {
    throw new RuntimeException('Unable to create ' . $destination);
  }
};
$copy_if_missing($default_settings, $site_directory . '/settings.php');
$settings_file = $site_directory . '/settings.php';
$contents = file_get_contents($settings_file);
$marker = '// Project settings loader.';
if (!str_contains($contents, $marker)) {
  $include = <<<'PHP'

// Project settings loader.
if (is_readable(__DIR__ . '/settings.local.php')) {
  require_once __DIR__ . '/settings.local.php';
}

PHP;
  if (file_put_contents($settings_file, $include, FILE_APPEND) === FALSE) {
    throw new RuntimeException('Unable to enable the project settings loader.');
  }
}

$source_root = $project_root . ($mode === 'local' ? '/.lando' : '/.github');
$copy_if_missing($source_root . '/drupal/settings.local.php', $site_directory . '/settings.local.php');
if (!is_dir($project_root . '/drush/sites')) {
  mkdir($project_root . '/drush/sites', 0755, TRUE);
}
$copy_if_missing($source_root . '/drush/drush.yml', $project_root . '/drush/drush.yml');
$copy_if_missing($source_root . '/drush/self.site.yml', $project_root . '/drush/sites/self.site.yml');

if ($mode === 'local') {
  foreach (['private/files', 'tmp', 'web/sites/default/files'] as $directory) {
    if (!is_dir($project_root . '/' . $directory)) {
      mkdir($project_root . '/' . $directory, 0775, TRUE);
    }
  }
  foreach (['secrets.local.php', 'secrets.php'] as $filename) {
    $secret_path = $project_root . '/' . $filename;
    if (!is_file($secret_path)) {
      $previous_umask = umask(0077);
      try {
        $secrets = file_get_contents($project_root . '/.lando/drupal/' . $filename);
        if ($filename === 'secrets.local.php') {
          $salt = bin2hex(random_bytes(48));
          $secrets .= "\n\$settings['hash_salt'] = " . var_export($salt, TRUE) . ";\n";
        }
        $handle = fopen($secret_path, 'x');
        if ($handle === FALSE) {
          throw new RuntimeException('Unable to create ' . $filename . '.');
        }
        fwrite($handle, $secrets);
        fclose($handle);
      }
      finally {
        umask($previous_umask);
      }
    }
  }
}

echo "Prepared {$mode} settings; existing settings and credentials were preserved.\n";
