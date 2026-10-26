# @@SITE_NAME@@

A Composer-managed, single-site Drupal project with a `web/` document root and Lando development environment.

## Get started

Requirements: Docker, current Lando with its Drupal/PHP/MariaDB/Node/MailHog plugins, Python 3.9+, Bash and Git 2.28+. PHP, Composer, Drush and npm run inside Lando.

```bash
./scripts/setup.sh
```

On a new workspace this downloads the latest stable official `drupal/recommended-project` through **Lando Composer**, adds Drush, patch management and development tools, installs dependencies, prepares local settings, and installs the selected core profile. Subsequent runs install the committed `composer.lock` and preserve the database, settings and credentials. A failed setup can be resumed with the same command.

Site: **@@LOCAL_URL@@**. Mail viewer: **http://mail.@@MACHINE_NAME@@.lndo.site**. Use `lando info` for the automatically allocated database and mail ports. Custom local hostnames need working DNS or a hosts-file entry pointing to `127.0.0.1`.

The administrator password is randomly generated. Sign in and set your own password:

```bash
lando drush uli
```

Use `./scripts/setup.sh --no-install` to install dependencies without touching the database, or `lando install` to install an empty local database later. The installer refuses a nonempty database unless Drupal already bootstraps, in which case it preserves the installation.

## Daily development

```bash
lando start
lando composer install
lando drush status
lando drush cr
lando composer quality
lando stop
```

Keep custom modules in `web/modules/custom`, themes in `web/themes/custom`, and profiles in `web/profiles/custom`. Put module documentation in the project-root `docs/<module_name>/README.md` and module-specific agent guidance in `docs/<module_name>/AGENTS.md`. Read the root `AGENTS.md` and the module's documentation before making changes. Follow the [documentation conventions and module index](docs/README.md): document current behavior and services, keep READMEs current with implementation changes, and prefix module README headings with fitting emojis.

Node 24 is available through `lando npm`. Add a theme's package manifest and build commands when the project needs a frontend build; the template does not assume a particular theme or framework.

## Layout

| Path | Purpose |
| --- | --- |
| `.lando.yml`, `.lando/` | Local services, PHP settings, Drupal loaders and Drush templates |
| `.github/workflows/` | Quality checks and reusable dev, test and production deployments |
| `.github/drupal/`, `.github/drush/` | Deployment settings loaders and Drush defaults |
| `composer.json`, `composer.lock` | Project dependencies and exact installed versions |
| `patches.json`, `patches/`, `patches.lock.json` | Patch definitions, local patch files and checksums |
| `config/default/` | Shared configuration exports, outside the document root |
| `config/{local,dev,test,prod}/` | Empty directories reserved for optional Config Split exports |
| `drush/` | Generated local configuration plus project-owned custom commands |
| `scripts/` | Setup, installation, quality checks, release and deployment helpers |
| `docs/` | Custom module READMEs, agent guidance and module index, outside the web root |
| `templates/` | Examples for local overrides, remote aliases and private server settings |
| `project.json` | Non-secret bootstrap choices; changes are read by future installations |
| `private/`, `tmp/` | Ignored local private files and temporary data |

Drupal core, contributed extensions, recipes, libraries, vendor dependencies and scaffolded entry points are supplied by Composer and ignored by Git. Keep `composer.lock` and `patches.lock.json` committed. The initial scaffold's `*` core constraints are replaced by the official project's constraints during the first setup.

Shared commit-message, documentation and release-note guidelines live in `AGENTS.md`. Provide concise commit messages when requested, explain non-obvious decisions in commit notes, and keep module READMEs focused on current behavior rather than change history. Agents prepare requested local work; the user runs all pushes.

## Configuration

The generator creates directory placeholders only. It copies no site configuration, content, UUIDs, custom code or patches from another project. A normal fresh installation creates active core configuration in the database.

```bash
lando drush cex -y             # Export this site's configuration
lando drush config:status     # Review drift
lando drush cim -y             # Import reviewed exports
lando drush cr
```

Export and commit the site's first configuration before enabling deployment. Config Split is optional and is not installed or activated: add it with Composer and create its split definitions if environment-specific exports become necessary. Empty split directories have no runtime effect.

When updating Drupal, review patch compatibility and upstream release notes, then run:

```bash
lando composer update 'drupal/core-*' --with-all-dependencies
lando drush updb -y
lando drush cr
lando drush cex -y
lando composer quality
```

Deployments use `drush deploy`: database updates run before configuration import, followed by cache rebuilds and deployment hooks. Updates must not depend on configuration from the same deployment already being imported.

## Settings, secrets and mail

Local setup automatically creates and connects these files:

- `web/sites/default/settings.php`: generated from Drupal's default settings, with the local-settings include enabled.
- `web/sites/default/settings.local.php`: copied from `.lando/drupal/settings.local.php`; loads database credentials from `LANDO_INFO` and configures local paths and trusted hosts.
- Root `secrets.local.php`: created with a **unique persistent hash salt**.
- Root `secrets.php`: created for your integration credentials and private overrides; loads after `secrets.local.php`.

The local settings filename is `settings.local.php`. All generated settings and secrets files are ignored by Git; secrets stay outside the web root and are excluded from deployment uploads. Existing settings and credentials are preserved when setup runs again. Do not export credentials into configuration.

Existing generated settings and Drush files are preserved. After intentionally changing a tracked loader/template, update or remove its generated counterpart and rerun `lando php scripts/prepare-settings.php local`. The secrets file is preserved.

Lando routes PHP's default mail transport to MailHog. When adding an SMTP integration, configure its local transport to `mailhog:1025` in private overrides. The template does not install an application-specific mail module.

Copy examples from `templates/` for local env overrides and Xdebug. After changing Lando service configuration, run `lando rebuild -y`. `scripts/run-cron-every-minute.sh` runs cron explicitly while developing; no background cron package is installed automatically. Add an appropriate cron schedule to your hosting environment.

## Quality checks

```bash
lando composer lint
lando composer lint:fix
lando composer phpstan
lando composer test           # Unit tests
lando composer test:kernel
lando composer test:functional
lando composer test:js
bash scripts/tests/launch-testing-release.test.sh
```

Blank custom directories and absent test suites are reported explicitly. Add meaningful tests with the first feature. The default quality command checks PHP syntax, Drupal coding standards, PHPStan and unit tests.

Kernel and browser suites require an explicit `SIMPLETEST_DB` pointing to a **separate test database**. An example test database service is provided in `templates/.lando.local.yml`; after copying/adapting it, rebuild Lando. Browser suites also need `SIMPLETEST_BASE_URL`; JavaScript suites need a compatible WebDriver service and `MINK_DRIVER_ARGS_WEBDRIVER`. Never reuse the development database. Core test bootstrap and tooling versions come from the matching `drupal/core-dev` package.

## GitHub setup and deployments

The generator creates a local Git repository with `main` as its initial branch unless `--no-git` was requested. It supplies the project's `.gitignore` and records an `origin` URL when provided. Git metadata belongs to this generated project, independently of the generator repository. Creating the first commit and publishing to GitHub remain explicit steps. After reviewing the generated files and completing setup:

```bash
git add .
git commit -m 'Initialize Drupal project'
git branch codex
# Add an origin if it was not supplied to the generator, then push as usual.
```

Quality checks run for pull requests and pushes to `main` and `codex`. Configure branch protection and required checks in GitHub.

Deployment is opt-in: set the **repository variable** `DEPLOY_ENABLED=true` after provisioning hosting. Create GitHub environments named `dev`, `test`, and `prod`. Configure these values separately in each environment:

| Type | Name | Example / purpose |
| --- | --- | --- |
| Variable | `SSH_HOST` | Deployment host |
| Variable | `SSH_USER` | Deployment account |
| Variable | `SSH_PORT` | Optional; defaults to `22` |
| Variable | `DEPLOY_ROOT` | `/srv/www/example`; absolute path, no spaces or trailing slash |
| Variable | `SITE_URI` | Canonical `https://` site URL |
| Variable | `INITIAL_INSTALL` | Set `true` for the first deployment to an empty database; remove after success |
| Secret | `SSH_PRIVATE_KEY` | Deployment private key |
| Secret | `SSH_KNOWN_HOSTS` | Host key entries verified independently; include `[host]:port` for a custom SSH port |

Use environment protection rules for production approvals. Deployments are serialized per environment. `main` deploys to **dev**, stable `vX.Y.Z` tags deploy to **test**, and **prod** requires manually dispatching `prod_deploy.yml` with a tested tag. The reusable workflow checks out that exact tag and validates that it belongs to `main`; it runs quality checks before installing production dependencies.

### Hosting contract

The deployment account needs Linux, Bash, PHP @@PHP_VERSION@@ with Drupal's extensions, a compatible database client, rsync, tar and gzip. Provision the database and point the webserver document root at `DEPLOY_ROOT/live/web`. The webserver must allow symlinks and write to the shared public/private/tmp directories.

Create `DEPLOY_ROOT/shared/settings.local.php` from `templates/server.settings.local.php`, replacing the database values, trusted hosts and hash salt on the server. Optional credentials belong in `shared/secrets.php` (or `shared/secrets.local.php`, loaded first). Keep these files readable by PHP and inaccessible from the public web root. Do not reuse salts or production credentials across environments.

The resulting server layout is:

```text
DEPLOY_ROOT/
  live -> releases/RELEASE
  releases/RELEASE/           # Immutable code, config and Composer dependencies
  shared/settings.local.php  # Server-owned database/settings
  shared/secrets.php         # Server-owned integration credentials
  shared/files/              # Persistent public uploads
  shared/private/            # Persistent private uploads
  shared/tmp/
  backups/RELEASE/            # Database and public/private file backups
```

For the first deployment, enable `INITIAL_INSTALL=true` only after exporting site configuration and provisioning an empty database. The deployment refuses initial installation if **any tables exist**. Retrieve an administrator login on the server with `php DEPLOY_ROOT/live/vendor/bin/drush --root=DEPLOY_ROOT/live/web --uri=SITE_URI uli`, then remove `INITIAL_INSTALL`.

For subsequent deployments, the live site must bootstrap. The script enables maintenance mode, makes required database and file backups, runs the staged release's `drush deploy`, switches `live` to the new release, and disables maintenance mode. Shared files and secrets stay outside releases and are excluded from uploads. Backups and previous releases are retained; configure retention appropriate to the project.

A failed deployment stops and may leave maintenance mode enabled. Inspect the failing phase and database before retrying. A code symlink change does not undo database updates: restore the matching database/files backup and code together when rollback requires it. Deployment cannot guarantee transactions across schema updates or prevent external cron/queue writers; pause those writers for production migrations when needed.

Remote Drush aliases are optional. Adapt `templates/self.site.yml.example` into `.lando/drush/self.site.yml`. Alias `root` values point to the Drupal `web` directory. No application-specific synchronization commands are installed.

## Launch a release to test

Push `codex`, merge its PR into `main`, and start with a clean worktree:

```bash
./scripts/launch-testing-release.sh
```

The helper verifies branch synchronization, fetches `main`, prepares release notes, waits while you publish a GitHub release with a stable `vX.Y.Z` tag, verifies the tag matches `origin/main`, then fast-forwards and pushes `codex`. It supports the first release without a previous tag. If Codex CLI is installed it generates notes using existing authentication and `--ignore-user-config`, with the complete `Release Notes Requests` section from `AGENTS.md` passed verbatim in its prompt. A missing or empty section stops generation. Without Codex, Git history and diff information are printed for manual notes. Nothing is published automatically by the helper until you publish the GitHub release; its final push synchronizes `codex`.

Check the test deployment workflow and the deployed site before manually dispatching production. The helper verifies Git state; it does not wait for deployment completion.
