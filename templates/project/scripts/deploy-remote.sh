#!/usr/bin/env bash
# Server contract: Linux, PHP CLI, rsync, tar, gzip, and the database client.
set -Eeuo pipefail
root=${1:?Missing deployment root}
uri=${2:?Missing site URI}
release_id=${3:?Missing release id}
initial_install=${4:-false}
[[ $root =~ ^/[a-zA-Z0-9_./-]+$ && $root != / && $root != */ && $root != *//* \
  && $root != */../* && $root != */.. && $root != */./* && $root != */. ]] || exit 2
[[ $release_id =~ ^[a-zA-Z0-9-]+$ && $uri =~ ^https?://[a-zA-Z0-9][a-zA-Z0-9.:-]*/?$ ]] || exit 2
release="$root/releases/$release_id"
shared="$root/shared"
fail() { printf 'Deployment stopped: %s\n' "$1" >&2; exit 1; }
trap 'printf "Deployment failed. Inspect the current release and database before retrying; maintenance may remain enabled.\n" >&2' ERR

[[ -f $shared/settings.local.php && -f $release/web/index.php && -f $release/vendor/bin/drush ]] || fail 'Provision shared/settings.local.php and upload a complete release first.'
[[ -f $release/config/default/core.extension.yml ]] || fail 'Release configuration is missing.'
[[ ! -e $root/live || -L $root/live ]] || fail 'live must be a symlink to a release directory.'
mkdir -p "$shared/files" "$shared/private" "$shared/tmp"
[[ ! -e $release/web/sites/default/files ]] || fail 'The artifact must not contain public files.'
ln -s "$shared/files" "$release/web/sites/default/files"
drush=(php "$release/vendor/bin/drush" "--root=$release/web" "--uri=$uri")

if [[ -L $root/live ]]; then
  previous=(php "$root/live/vendor/bin/drush" "--root=$root/live/web" "--uri=$uri")
  [[ $("${previous[@]}" status --field=bootstrap) == Successful ]] || fail 'The live site cannot bootstrap; refusing to change it.'
  "${previous[@]}" state:set system.maintenance_mode 1 --yes
  "${previous[@]}" cache:rebuild
  backup="$root/backups/$release_id"
  mkdir -m 700 -p "$backup"
  (
    umask 0077
    "${previous[@]}" sql:dump --result-file="$backup/database.sql"
    gzip "$backup/database.sql"
    tar -czf "$backup/files.tar.gz" -C "$shared" files private
  )
  # Failures stop before activation. Database migrations may already have run;
  # restoring old code alone would not roll back the database.
  "${drush[@]}" deploy --yes
else
  [[ $initial_install == true ]] || fail 'First deployment needs the environment variable INITIAL_INSTALL=true and an empty database.'
  tables=$("${drush[@]}" sql:query 'SHOW TABLES' --extra=--skip-column-names)
  [[ -z ${tables//[[:space:]]/} ]] || fail 'Initial installation requires a completely empty database.'
  password=$(php -r 'echo bin2hex(random_bytes(32));')
  "${drush[@]}" site:install --existing-config --yes --account-name=admin "--account-pass=$password"
  unset password
fi

ln -s "$release" "$root/.live-$release_id"
mv -Tf "$root/.live-$release_id" "$root/live"
"${drush[@]}" state:set system.maintenance_mode 0 --yes
"${drush[@]}" cache:rebuild
printf 'Deployed %s to %s. Backups and prior releases were retained.\n' "$release_id" "$uri"
