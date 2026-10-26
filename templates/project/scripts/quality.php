<?php

/**
 * @file
 * Run installed quality tools, including clean handling of an empty new site.
 */

declare(strict_types=1);

$root = dirname(__DIR__);
chdir($root);
$mode = $argv[1] ?? '';
$run = static function (array $command): void {
  $process = proc_open($command, [STDIN, STDOUT, STDERR], $pipes);
  $code = is_resource($process) ? proc_close($process) : 1;
  if ($code !== 0) {
    exit($code);
  }
};
$files_under = static function (array $directories): array {
  $files = [];
  foreach ($directories as $directory) {
    if (!is_dir($directory)) {
      continue;
    }
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS));
    foreach ($iterator as $file) {
      if ($file->isFile() && !preg_match('~/(node_modules|vendor)/~', $file->getPathname())) {
        $files[] = $file->getPathname();
      }
    }
  }
  return $files;
};
$custom = $files_under(['web/modules/custom', 'web/themes/custom', 'web/profiles/custom']);
$php_files = array_filter($custom, static fn(string $path): bool => (bool) preg_match('/\.(php|module|inc|install|profile|theme|test)$/', $path));

switch ($mode) {
  case 'lint':
  case 'lint:fix':
    foreach ($files_under(['scripts', '.lando/drupal', '.github/drupal']) as $path) {
      if (str_ends_with($path, '.php')) {
        $run([PHP_BINARY, '-l', $path]);
      }
    }
    $lintable = array_filter($custom, static fn(string $path): bool => (bool) preg_match('/\.(php|module|inc|install|profile|theme|test|yml)$/', $path));
    if (!$lintable) {
      echo "No custom Drupal files to check yet.\n";
      break;
    }
    $tool = $mode === 'lint' ? 'phpcs' : 'phpcbf';
    $run([PHP_BINARY, 'vendor/bin/' . $tool, '--standard=phpcs.xml.dist']);
    break;

  case 'phpstan':
    if (!$php_files) {
      echo "No custom PHP to analyze yet.\n";
      break;
    }
    $run([PHP_BINARY, 'vendor/bin/phpstan', 'analyse', '-c', 'phpstan.neon.dist', '--memory-limit=1G']);
    break;

  case 'test':
  case 'test:kernel':
  case 'test:functional':
  case 'test:js':
    $suite = match ($mode) {
      'test' => 'unit',
      'test:kernel' => 'kernel',
      'test:functional' => 'functional',
      'test:js' => 'functional-javascript',
    };
    $directory = match ($suite) {
      'unit' => 'Unit',
      'kernel' => 'Kernel',
      'functional' => 'Functional',
      'functional-javascript' => 'FunctionalJavascript',
    };
    $tests = array_filter($files_under(['tests', 'web/modules/custom', 'web/themes/custom']),
      static fn(string $path): bool => (bool) preg_match('~(?:^|/)tests/src/' . $directory . '/~', $path) && str_ends_with($path, 'Test.php'));
    if (!$tests) {
      echo "No {$suite} tests exist yet. Add tests with your first feature.\n";
      break;
    }
    if ($suite !== 'unit' && !getenv('SIMPLETEST_DB')) {
      fwrite(STDERR, "Set SIMPLETEST_DB to an isolated test database before running this suite.\n");
      exit(1);
    }
    if (in_array($suite, ['functional', 'functional-javascript'], TRUE)) {
      if (!getenv('SIMPLETEST_BASE_URL')) {
        fwrite(STDERR, "Set SIMPLETEST_BASE_URL for browser tests.\n");
        exit(1);
      }
      $output = getenv('BROWSERTEST_OUTPUT_DIRECTORY') ?: '/tmp/drupal-browser-output';
      if (!is_dir($output)) {
        mkdir($output, 0775, TRUE);
      }
    }
    $run([PHP_BINARY, 'vendor/bin/phpunit', '-c', 'phpunit.xml.dist', '--testsuite', $suite]);
    break;

  default:
    fwrite(STDERR, "Unknown quality command. Use lint, lint:fix, phpstan, test, test:kernel, test:functional or test:js.\n");
    exit(2);
}
