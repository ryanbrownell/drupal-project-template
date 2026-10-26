#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
printf 'Running Drupal cron every minute. Press Ctrl+C to stop.\n'
while true; do
  started=$(date +%s)
  lando drush cron
  elapsed=$(( $(date +%s) - started ))
  if (( elapsed < 60 )); then
    sleep "$((60 - elapsed))"
  fi
done
