<?php

/**
 * @file
 * Local Lando settings. Credentials and the salt stay outside the web root.
 */

$lando = json_decode(getenv('LANDO_INFO') ?: '{}', TRUE, 512, JSON_THROW_ON_ERROR);
if (!empty($lando['database'])) {
  $database = $lando['database'];
  $databases['default']['default'] = [
    'database' => $database['creds']['database'],
    'username' => $database['creds']['user'],
    'password' => $database['creds']['password'],
    'host' => $database['internal_connection']['host'],
    'port' => $database['internal_connection']['port'],
    'driver' => 'mysql',
    'namespace' => 'Drupal\\mysql\\Driver\\Database\\mysql',
    'autoload' => 'core/modules/mysql/src/Driver/Database/mysql/',
    'prefix' => '',
  ];
}

$project_root = dirname($app_root);
$settings['config_sync_directory'] = $project_root . '/config/default';
$settings['file_private_path'] = $project_root . '/private/files';
$settings['file_temp_path'] = $project_root . '/tmp';
$settings['trusted_host_patterns'] = [@@TRUSTED_HOST_PHP@@, '^localhost$'];
$settings['skip_permissions_hardening'] = TRUE;

foreach (['secrets.local.php', 'secrets.php'] as $filename) {
  if (is_readable($project_root . '/' . $filename)) {
    require $project_root . '/' . $filename;
  }
}
