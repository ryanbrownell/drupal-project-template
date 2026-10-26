name: Quality checks

on:
  pull_request:
  push:
    branches: [main, codex]
  workflow_dispatch:
  workflow_call:
    inputs:
      ref:
        type: string
        required: false
        default: ''

permissions:
  contents: read

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ inputs.ref || github.sha }}
          persist-credentials: false
      - name: Set up PHP
        uses: shivammathur/setup-php@v2
        with:
          php-version: '@@PHP_VERSION@@'
          extensions: gd, pdo_mysql, pdo_sqlite, intl, mbstring, zip
          tools: composer:v2
          coverage: none
      - name: Validate locked dependencies
        run: composer validate --strict --check-lock
      - name: Locate Composer download cache
        id: composer-cache
        run: echo "path=$(composer config cache-files-dir)" >> "$GITHUB_OUTPUT"
      - uses: actions/cache@v5
        with:
          path: ${{ steps.composer-cache.outputs.path }}
          key: composer-${{ runner.os }}-php-@@PHP_VERSION@@-${{ hashFiles('composer.lock') }}
          restore-keys: composer-${{ runner.os }}-php-@@PHP_VERSION@@-
      - name: Install locked dependencies
        run: composer install --prefer-dist --no-interaction --no-progress
      - name: Check PHP and Drupal coding standards, static analysis and unit tests
        run: composer quality
      - name: Check release and deployment scripts
        run: |
          bash -n scripts/launch-testing-release.sh scripts/deploy.sh scripts/deploy-remote.sh
          bash scripts/tests/launch-testing-release.test.sh
