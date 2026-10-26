<?php

/**
 * @file
 * Settings for DEPLOY_ROOT/releases/RELEASE/web, also reached through live/web.
 */

$release_root = dirname(realpath($app_root) ?: $app_root);
$shared_root = dirname($release_root, 2) . '/shared';
$settings['config_sync_directory'] = $release_root . '/config/default';
$settings['file_private_path'] = $shared_root . '/private';
$settings['file_temp_path'] = $shared_root . '/tmp';

if (!is_readable($shared_root . '/settings.local.php')) {
  throw new \RuntimeException('Provision shared/settings.local.php before deploying.');
}
require $shared_root . '/settings.local.php';
foreach (['secrets.local.php', 'secrets.php'] as $filename) {
  if (is_readable($shared_root . '/' . $filename)) {
    require $shared_root . '/' . $filename;
  }
}
