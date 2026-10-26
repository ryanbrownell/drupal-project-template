<?php

/**
 * @file
 * Copy to DEPLOY_ROOT/shared/settings.local.php on the server and edit there.
 * Give each environment its own database, trusted hosts and persistent salt.
 */

$databases['default']['default'] = [
  'driver' => 'mysql',
  'namespace' => 'Drupal\\mysql\\Driver\\Database\\mysql',
  'autoload' => 'core/modules/mysql/src/Driver/Database/mysql/',
  'database' => 'REPLACE_DATABASE',
  'username' => 'REPLACE_USER',
  'password' => 'REPLACE_PASSWORD',
  'host' => 'localhost',
  'port' => 3306,
  'prefix' => '',
];
$settings['hash_salt'] = 'REPLACE_WITH_A_UNIQUE_RANDOM_VALUE';
$settings['trusted_host_patterns'] = ['^www\\.example\\.invalid$'];
