<?php

/**
 * @file
 * Install the local site without replacing an existing or unrelated database.
 */

declare(strict_types=1);

if (!getenv('LANDO_INFO')) {
  fwrite(STDERR, "This installer is for Lando. Run lando install.\n");
  exit(1);
}

$project_root = dirname(__DIR__);
require $project_root . '/vendor/autoload.php';
require __DIR__ . '/prepare-settings.php';
$project = json_decode(file_get_contents($project_root . '/project.json'), TRUE, 512, JSON_THROW_ON_ERROR);
$drush = [PHP_BINARY, $project_root . '/vendor/bin/drush', '--root=' . $project_root . '/web', '--uri=' . $project['url']];
$run = static function (array $arguments, bool $capture = FALSE) use ($drush, $project_root): string {
  $descriptors = [STDIN, $capture ? ['pipe', 'w'] : STDOUT, STDERR];
  $process = proc_open(array_merge($drush, $arguments), $descriptors, $pipes, $project_root);
  $output = $capture && is_resource($process) ? stream_get_contents($pipes[1]) : '';
  if ($capture && isset($pipes[1])) {
    fclose($pipes[1]);
  }
  if (!is_resource($process) || proc_close($process) !== 0) {
    throw new RuntimeException('Drush failed; correct the cause before retrying.');
  }
  return trim($output);
};

// Ask Drush about the effective connection, including private DB overrides.
// A failed SQL query must not be interpreted as an empty database.
if ($run(['sql:query', 'SHOW TABLES', '--extra=--skip-column-names'], TRUE) !== '') {
  if ($run(['status', '--field=bootstrap'], TRUE) === 'Successful') {
    echo "Drupal is already installed; the database and administrator were preserved.\n";
    exit(0);
  }
  fwrite(STDERR, "The database contains tables but Drupal cannot bootstrap. Refusing to reinstall.\n");
  exit(1);
}

$run([
  'site:install', $project['profile'], '--yes',
  '--site-name=' . $project['site_name'],
  '--site-mail=' . $project['email'],
  '--account-name=' . $project['admin_name'],
  '--account-mail=' . $project['email'],
  '--account-pass=' . bin2hex(random_bytes(24)),
  '--locale=' . $project['locale'],
]);
$run(['config:set', 'system.date', 'timezone.default', $project['timezone'], '--yes']);
$run(['cache:rebuild']);
echo "Drupal installed. Use lando drush uli to sign in and set your password.\n";
