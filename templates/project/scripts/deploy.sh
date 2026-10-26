#!/usr/bin/env bash
# Run by GitHub Actions after dependencies and deployment settings are built.
set -Eeuo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

fail() { printf 'Deployment stopped: %s\n' "$1" >&2; exit 1; }
for variable in SSH_HOST SSH_USER DEPLOY_ROOT SITE_URI; do
  [[ -n ${!variable:-} ]] || fail "Missing $variable. Configure the GitHub environment."
done
SSH_PORT=${SSH_PORT:-22}
INITIAL_INSTALL=${INITIAL_INSTALL:-false}
[[ $SSH_HOST =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || fail 'Invalid SSH_HOST.'
[[ $SSH_USER =~ ^[a-z_][a-z0-9_-]*$ ]] || fail 'Invalid SSH_USER.'
[[ $SSH_PORT =~ ^[0-9]{1,5}$ ]] && (( 10#$SSH_PORT > 0 && 10#$SSH_PORT <= 65535 )) || fail 'Invalid SSH_PORT.'
[[ $DEPLOY_ROOT =~ ^/[a-zA-Z0-9_./-]+$ && $DEPLOY_ROOT != / && $DEPLOY_ROOT != */ && $DEPLOY_ROOT != *//* \
  && $DEPLOY_ROOT != */../* && $DEPLOY_ROOT != */.. && $DEPLOY_ROOT != */./* && $DEPLOY_ROOT != */. ]] \
  || fail 'Use an absolute DEPLOY_ROOT without traversal, trailing slash or shell characters.'
[[ $SITE_URI =~ ^https?://[a-zA-Z0-9][a-zA-Z0-9.-]*(:[0-9]+)?/?$ ]] || fail 'Invalid SITE_URI.'
[[ $INITIAL_INSTALL == true || $INITIAL_INSTALL == false ]] || fail 'INITIAL_INSTALL must be true or false.'
[[ -f config/default/core.extension.yml ]] || fail 'Export and commit site configuration before deploying: lando drush cex -y'
[[ -f composer.lock && -f web/sites/default/settings.local.php && -f vendor/autoload.php ]] || fail 'Build the Composer artifact and deployment settings first.'

release_id="$(date -u +%Y%m%d%H%M%S)-$(git rev-parse --short=12 HEAD)-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
[[ $release_id =~ ^[a-zA-Z0-9-]+$ ]] || fail 'Invalid release identifier.'
ssh_options=(-p "$SSH_PORT" -o BatchMode=yes -o StrictHostKeyChecking=yes)
remote="$SSH_USER@$SSH_HOST"
release_path="$DEPLOY_ROOT/releases/$release_id"

# Inputs are restricted above because OpenSSH serializes remote arguments.
ssh "${ssh_options[@]}" "$remote" "mkdir -p '$release_path'"
rsync -az --delete --exclude-from=.github/deploy-excludes \
  -e "ssh -p $SSH_PORT -o BatchMode=yes -o StrictHostKeyChecking=yes" \
  ./ "$remote:$release_path/"
ssh "${ssh_options[@]}" "$remote" bash -s -- \
  "$DEPLOY_ROOT" "$SITE_URI" "$release_id" "$INITIAL_INSTALL" < scripts/deploy-remote.sh
