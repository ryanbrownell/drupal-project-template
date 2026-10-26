# AGENTS.md — @@SITE_NAME@@

## Scope and expectations

This is a single-site, Composer-managed Drupal project with a `web/` document root and Lando development environment. Act as a senior Drupal/PHP engineer. Keep changes focused, complete, reviewable and consistent with existing project patterns.

- Read the root README and, before working in a custom module, its `docs/<module_name>/README.md` and any `docs/<module_name>/AGENTS.md`. Search for compatible existing services and patterns before adding new ones.
- Use the installed Drupal version's APIs and PHP @@PHP_VERSION@@ features. Do not edit Composer-managed core, contributed code, libraries or vendor files directly.
- Keep custom modules, themes and profiles under `web/{modules,themes,profiles}/custom`.
- Prefer services and constructor injection. Keep controllers thin, route access explicit, and logging actionable.
- Use Drupal and DrupalPractice standards, configuration schemas, render arrays and precise cache tags/contexts. Escape output and validate input. Use CSRF protection for state changes.
- Queue or batch long-running work. Mock external services in tests and choose the smallest useful Unit/Kernel/Functional/FunctionalJavascript coverage.
- Reuse Drupal's behaviors and frontend patterns. Avoid CSS `!important`.

## Local tools and validation

Run PHP-dependent commands through Lando, including one-off PHP, Composer, Drush, PHPCS, PHPStan and PHPUnit. CI runs equivalent commands natively. Use `lando npm` for Node tooling.

```bash
./scripts/setup.sh
lando composer quality
lando drush config:status
lando drush cr
```

After changes affecting discovery or rendering, rebuild Drupal caches. Activate intentional configuration with `lando drush cim -y` and apply update hooks with `lando drush updb -y` when safe. Check pending config first; do not import unrelated changes silently. Report commands actually run and any validation that could not be performed.

Keep test databases separate from the development database. Kernel/Functional suites require an explicit `SIMPLETEST_DB`. Do not introduce live network calls into tests. A new project has no application tests; add meaningful coverage with features instead of placeholder tests.

## Configuration and updates

- Export shared config to `config/default/`, outside the document root. Review exports and commit intentional changes only.
- `config/{local,dev,test,prod}/` are empty reserved directories. Config Split is inactive unless explicitly installed and configured.
- Use update hooks for schema and data changes. Deployment runs updates before importing config; updates cannot depend on the new imported configuration. Use a post-import deploy hook where appropriate.
- Do not rewrite update hooks that may have run in a released environment. Add an idempotent follow-up update.
- Installable custom modules must not rely on this site's config exports for their module defaults.

## Secrets and dependencies

- Never commit credentials, database dumps, real salts or generated local settings. Setup creates `web/sites/default/settings.local.php` and both root secrets files. Local secrets load from `secrets.local.php` (persistent salt), followed by `secrets.php` (integration credentials/overrides). Existing files are preserved. Hosting loads server-owned `shared/settings.local.php`, followed by optional `shared/secrets.local.php` and `shared/secrets.php`.
- Use `$settings` for integration secrets and runtime `$config` overrides only where required. Never save credentials into exported configuration or expose them in browser settings/logs.
- Commit `composer.json`, `composer.lock`, `patches.json`, local patches and `patches.lock.json` together when relevant. Use Composer Patches 2.x; document each patch's upstream issue and removal condition in `patches/README.md`.
- Check upstream changes and patch compatibility before updating dependencies. Install locked dependencies on other environments.
- Settings preparation preserves existing local files. Update generated counterparts intentionally after changing tracked settings or Drush templates.

## Documentation

- Document module-specific functionality in `docs/<module_name>/README.md` under the project root, keep it current with every change, and ensure it reflects only the current state (no references to removed functionality or patterns). Do not store module READMEs under `web/`.
- Module-specific agent guidance files must live under `docs/<module_name>/AGENTS.md`. Do not keep module `AGENTS.md` files under `web/modules/*`.
- Before working in any custom module, review its README and any module-specific agent guidance. Create the module's documentation alongside its first implementation and update it in the same change as the behavior it describes.
- Keep module README entries behavior-focused: features, flows, access, APIs and data contracts. Avoid transient implementation/styling details unless explicitly requested; include durable implementation details when operationally important, such as security, caching, performance or migration constraints.
- Do not use module READMEs as a changelog: avoid listing individual update hook IDs, one-off bugfixes or purely visual tweaks unless operationally critical.
- Keep a concise list of all services created by each module in its README, including each service's ID, purpose and behavior, to make reuse easy.
- Add a fitting emoji prefix to every heading in each module README.
- Explain non-obvious decisions in comments and commit notes. If behavior or architecture changes materially, update the relevant documentation.
- Keep this file, the root README, TODO and `docs/README.md` index current as conventions and modules evolve.

## Git and commit messages

- Provide a concise commit message when the user asks to create a commit.
- Keep changes focused and reviewable. Explain non-obvious decisions in commit notes, and include relevant test results and rationale for caching/access decisions when describing a change.
- Agents must not push to remote repositories. The user handles all `git push`, including force pushes. Local commits/history changes may be prepared within the user's requested scope.
- Do not publish releases or deploy unless the user explicitly requests it.

## Release Notes Requests

When asked for release notes "since <tag>":

- Treat the following as a mandatory checklist, not optional guidance.
- Default delivery is the assistant's final chat response only. Do not create,
  edit, or update release-note, changelog, README, or docs files unless the user
  explicitly asks for file output.
- If the user asks to save release notes but does not provide a target path, ask
  for the path before editing files.
- Analyze both commit history and code diffs between `<tag>` and `HEAD` so release notes reflect code changes, not just commit messages.
    - `git log --oneline <tag>..HEAD`
    - `git diff --stat <tag>..HEAD`
    - Spot-check key file diffs for notable behavior/config changes.
- Produce a short, user-facing release note with all of the following:
    - A clever, entertaining, amusing title (puns or other humour welcome) formatted as a Markdown H1 starting with `# ` so it can be pasted directly into GitHub. Place appropriate emojis after the headline text. Emojis must match the major themes/features in the changeset and should avoid smiley face emojis. Do not include the words "release notes" in the title/header.
        - Example: `# Text Me Maybe: SMS TFA Debut 📲🔐`
        - Emojis must come after the headline text and match the major themes/features in the changeset.
        - Titles must not include the words "release notes."
    - Use bullet points for the body so the notes are easy to scan and copy.
    - Keep the narrative feature-oriented, focused on user-visible impact, and written in objective language. Do not use first-person singular phrasing such as `I`.
    - Feature highlights, fixes, config changes, and docs/ops updates that summarize key changes without listing every changed file unless explicitly requested.
    - Tests added/updated and whether they were run.
    - Call out new modules/plugins/services and any access or caching changes.
- Unless the user explicitly asks for a different structure, use this output shape:
    - First line: `# <clever title> <matching emojis>`
    - Remaining lines: flat bullet points only
    - Include a bullet that explicitly states whether tests were run
- Keep it concise; list the most impactful changes only.
- Never assume tests ran unless explicitly executed.
- Before sending the answer, verify every release-notes response against this checklist:
    - Includes the Markdown H1 title
    - Emojis appear after the headline text
    - The title does not include the words `release notes`
    - The body uses bullet points
    - The body covers user-visible changes first
    - The body includes tests added/updated and whether they were run
    - The body mentions new modules/plugins/services and access/caching changes, even if the note is that none were introduced
    - No files were created or edited unless the user explicitly requested file output

## Release workflow

When Codex is installed, the release helper includes the `Release Notes Requests` section from this file verbatim in its prompt. Missing or empty instructions stop generation. Codex uses `--ignore-user-config` while retaining existing authentication.

The release helper is intended to be run by the user and includes a final push of `codex`. Its tests use isolated stubs and perform no remote writes:

```bash
bash scripts/tests/launch-testing-release.test.sh
```

GitHub quality checks run on pull requests and `main`/`codex`. Dev deploys from `main`, test from stable tags, and production by a manual tag dispatch. Deployment requires `DEPLOY_ENABLED=true`, per-environment variables/secrets, exported config, and provisioned hosting. Do not change those external settings as part of routine code work.
