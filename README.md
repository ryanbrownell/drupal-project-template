# Drupal project generator

Create a blank Drupal workspace with reusable setup, development and deployment conventions. The generated project is standalone and fetches Drupal through Lando Composer.

```bash
./create-project.sh
```

The interactive prompts collect site name, Lando machine name, destination, local URL, PHP version, database host port, core install profile, administrator username/email, timezone, and optional Git origin. Defaults use PHP 8.4, MariaDB 11.4, Node 24, MailHog, an automatically allocated database port, and core's **minimal** profile. Lando must have the corresponding service plugins installed.

No host PHP, Composer or npm is required. Install Docker, current Lando, Python 3.9+, Bash and Git 2.28+. Docker must be running and accessible to your user. On Windows, run in WSL2 with Lando/Docker configured there.

## Examples

```bash
# Prompt for details, then download dependencies and install a local site.
./create-project.sh ../my-drupal-site

# Accept defaults and supply selected values explicitly.
./create-project.sh ../client-site --yes \
  --site-name 'Client Website' \
  --url https://client.lndo.site \
  --email developer@example.com \
  --timezone America/Halifax

# Generate reviewable files without Docker, network access or Lando execution.
./create-project.sh ../client-site --yes --scaffold-only
cd ../client-site
./scripts/setup.sh

# Download dependencies while leaving the database untouched.
./create-project.sh ../another-site --yes --no-install

# Optional version selection; without this, Composer selects the stable project.
./create-project.sh ../pinned-major --yes --drupal-version '^11'
```

Run `./create-project.sh --help` for all options, including `--no-git`, `--profile standard`, `--database-port` and `--git-remote`. Non-interactive use requires `--yes`. Destinations must be new or completely empty; hidden files count. An existing nonempty project is never overwritten.

The generator initializes a local `main` repository unless `--no-git` is supplied. An optional origin is recorded locally. It does not create a commit, contact the origin, push, publish a GitHub repository, or deploy.

## What is generated

- Lando services and tooling, `.lando` PHP/Drupal/Drush templates, a local proxy URL, mail capture and local environment examples.
- A Composer project with Drush, Composer Patches 2.x, matching `drupal/core-dev`, Drupal coding standards, PHPStan and PHPUnit configuration.
- Empty `config/{default,local,dev,test,prod}` directories and custom code/test directories, tracked with `.gitkeep` files, plus a project-root `docs/README.md` index for custom module documentation.
- Reusable GitHub quality and deployment workflows: main → dev, stable tags → test, explicit tag dispatch → prod.
- A release-to-test helper that handles first and later releases, verifies main/codex synchronization, supports optional Codex notes and fast-forwards the development branch.
- Standalone setup/install/quality/cron/deployment scripts, private settings examples, root README, AGENTS and TODO, patch documentation, ignore and editor conventions.

The generated AGENTS.md preserves the source projects' generic commit-message, documentation and release-note rules: concise commit messages when requested, behavior-focused current documentation, module service inventories, emoji-prefixed module README headings, and feature-oriented release notes based on both history and diffs. The release helper passes that complete checklist verbatim to Codex and stops if the instructions are missing or empty. Custom module READMEs and agent guidance belong in root `docs/<module_name>/`, with modules indexed in `docs/README.md`. Agents do not push; pushes remain user-run.

The default full run starts Lando, runs `lando composer create-project drupal/recommended-project --no-install` in a temporary directory, merges the current official scaffold's metadata with the tooling manifest, then installs dependencies through Lando. The official core constraint also selects `drupal/core-dev`. It creates unique local secrets and installs a blank database. Core dependencies and entry points come from Composer.

`--scaffold-only` writes a preview Composer manifest with stable `*` core constraints. Run the generated `scripts/setup.sh` to replace those constraints with the official project's versions and create lock files. An optional stable version constraint is applied to the official project download. Runtime compatibility still applies; the supplied Lando recipe targets Drupal 11. A future Drupal major may require updating the supported PHP/Lando recipe.

Setup preserves state after a failure and can be rerun from the generated project. Clones use committed lock files instead of downloading a new project template. The local installer checks for database tables before calling site:install, preserves an installed site, and refuses a nonempty database that cannot bootstrap.

Full setup also creates `web/sites/default/settings.php`, enables its `settings.local.php` include, and creates `web/sites/default/settings.local.php` from the Lando template. The filename used by this project is `settings.local.php`. It automatically creates both root `secrets.local.php` with a unique persistent hash salt and root `secrets.php` for integration credentials/overrides. They load in that order, stay outside the web root, are ignored by Git and excluded from uploads, and are preserved on repeated setup. `--scaffold-only` supplies their tracked templates; the actual private files are created by `./scripts/setup.sh` after Composer supplies Drupal.

No source config exports, UUIDs, content, custom modules/themes, recipes, Drupal trees, database dumps, credentials, salts, Composer locks or application patches are copied. Config Split is optional and inactive; the reserved split directories are empty. The first configuration export is a deliberate project-development step.

## Source review

Two existing Drupal projects, a CMS project and a Commerce project, were examined at the project-tooling level. The review covered root manifests/documentation/ignore files; complete Lando definitions; `.lando/{drupal,drush,php}`; `.github/{drupal,drush,workflows}`; all top-level shell helpers; release/settings-loader regression tests; environment examples; patch metadata; quality-tool configuration; and directory structure. Application-specific test/config/code inventories were used only to identify exclusions. Drupal core, application modules/themes, recipes and config export contents were not used as template sources. Root secret files, certificates, keys and SQL dumps were not read or copied.

| Area | Source findings | Template decision |
| --- | --- | --- |
| Composer foundation | The CMS project uses Drupal CMS and many marketing/AI/recipe dependencies; the Commerce project uses recommended-project plus Commerce/integrations. Both target Drupal 11. | Download the current official recommended-project. Include core and development tooling; add application dependencies later. |
| Bootstrap | Both Lando builds run Composer before a new project's manifest/code necessarily exists, copy settings, and install from existing config. | Start an empty environment first; use a resumable external setup phase and guarded fresh profile install. |
| Lando services | PHP 8.3, Node 24, MailHog, MariaDB 10.11/11.4, hard-coded DB ports; the Commerce project has an advertising hostname. | Configurable PHP/URL/host port, MariaDB 11.4, Node 24 and MailHog; no application aliases. |
| Local env files | Both refer to defaults and local env files; the CMS project lacks its defaults file. | Supply tracked defaults and recreate ignored local overrides before Lando start. |
| Settings | Tracked fixed salts, application overrides, old database namespace, secret-loader differences. | Unique ignored salt, current mysql module namespace, stable local and server settings loaders, ordered private overrides. |
| Configuration | Actual layouts use `config/default` and environment directories. Some Commerce project docs instead describe `config/sync`. | Use `config/default` consistently; reserve all four split directories without copied exports or automatic split activation. |
| Drush | Reusable workstation/server template pattern; source aliases contain specific hosts/paths and root values at the Composer directory. | Keep the pattern, default to empty aliases and provide examples whose roots point to `web`. |
| Patches | The CMS project uses Patches 2.x and a lock; the Commerce project uses 1.x. All actual patches are application/core-version specific. | Standardize on Patches 2.x, external empty definitions, generated patch lock and documented repatching workflow. |
| Quality tools | The Commerce project has coding standards/static analysis/PHPUnit/Rector; some paths, PHPStan options and test DB defaults are stale or site-specific. | Use matching core-dev, current PHPStan configuration, empty-suite handling and explicit isolated test DBs. Defer Rector until needed. |
| Deployment workflows | Nearly duplicated dev/test/prod workflows; hard-coded infrastructure, no reliable selected-tag checkout for manual dispatch, unpinned host discovery, variable backup failure handling; the Commerce project adds a specific theme build. | Reusable, configurable workflow; exact tag checkout, explicit PHP, required backups, verified SSH hosts, shared persistent files, production environment protections. Add project-specific asset builds when a theme exists. |
| Upload exclusions | The CMS project explicitly excludes root secret files; the Commerce project lacks those two exclusions. | Exclude root secret/env files, local state, private data, dumps and keys in a shared exclusion file. |
| Release launcher | Both copies and tests are identical; require a previous release tag and Codex, then reset/push codex. | Preserve the tested authentication/config behavior; pass the current AGENTS.md release-note checklist verbatim; support initial releases and optional Codex; use fast-forward instead of hard reset and recheck branch state before pushing. |
| Other helpers | Global Docker log truncation, remote proxy tunnels, C3 cleanup, SQL collation conversion, production data sync and module view-export tasks depend on existing infrastructure or application code. | Keep an explicit local cron helper. Exclude infrastructure/global mutation and application-specific helpers. Use Docker log rotation settings. |
| Documentation | The CMS project retains a Drupal CMS/DDEV README; the Commerce project has useful workflow guidance mixed with business/integration instructions; TODO is application-specific. | Write a consistent generic README, agent guidance and project setup checklist. |
| Git/editor files | Source ignore rules hide root editor attributes and most Drush files. | Track editor attributes and project-owned Drush code; ignore generated Drush/settings files and Composer trees. |

The originals are unchanged. The generator has no runtime dependency on their directories.

## Hosting setup

Generated deployment workflows are complete but **disabled until repository variable `DEPLOY_ENABLED=true` is set**. The generated README lists all GitHub environment variables/secrets and the server filesystem contract. Hosting, DNS, databases, SSH keys and secrets require project-specific provisioning; the generator does not create external infrastructure.

Deployments use versioned releases and a `live` symlink with server-owned shared settings/files. This changes the source projects' live/stage directory swap to a reusable layout. First deployment requires exported configuration, an explicitly enabled initial install, and an empty database. Later deployments require a working live site and successful backups. Backups and releases are retained; configure retention. A failed schema migration requires inspecting/restoring the database as appropriate, not only switching code.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

The suite exercises real file rendering, input escaping, destination protection, Git initialization/ignores, interactive defaults, standalone/resumable setup through a stub Lando, source-independent use, and release/deployment failure paths with isolated local tools. Optional PyYAML adds YAML parsing checks; JSON and XML use the standard library. If a PHP CLI is available, additional tests execute the settings loaders, installer guards and quality helper against synthetic fixtures. Set `DRUPAL_TEMPLATE_TEST_PHP=/path/to/php` to select an isolated interpreter. These tests do not install Drupal or connect to a database/server.

The validation suite includes native PHP fixture checks, format/syntax checks and isolated integration tests. CI runs it with PHP 8.3 and 8.4. The generator and generated GitHub workflows can also be checked with `actionlint`.

A real Lando/Composer/Drupal installation and an actual SSH deployment still require validation in an environment with Docker/hosting access. In the development sandbox, Docker's socket is inaccessible and Lando's user config is read-only. An official Ubuntu PHP CLI was extracted only under `/tmp` to run the fixture tests; no host packages were installed. The checks do not verify Composer dependency resolution or container runtime behavior. To perform the real smoke test:

```bash
./create-project.sh /tmp/drupal-template-smoke --yes --no-git
cd /tmp/drupal-template-smoke
lando drush status
lando composer quality
./scripts/setup.sh
```

Inspect the site and a captured test email, confirm the second setup preserves its data, then stop/remove the disposable environment when finished.

## Upstream references

The bootstrap follows [Lando's Drupal quick start](https://docs.lando.dev/plugins/drupal/getting-started.html) and [Drupal's Composer project guidance](https://www.drupal.org/docs/develop/using-composer/manage-dependencies). Patch definitions follow [Composer Patches 2.x](https://docs.cweagans.net/composer-patches/usage/defining-patches/). Remote aliases follow [Drush's alias documentation](https://www.drush.org/13.x/site-aliases/); workflow composition and environment secrets follow [GitHub's reusable workflow documentation](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).
