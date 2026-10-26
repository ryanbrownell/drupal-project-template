# Project setup and follow-ups

- [ ] Define the site's requirements and implement its first custom feature/theme.
- [ ] Create `docs/<module_name>/README.md` with each custom module, document its services, and add it to `docs/README.md`; add module agent guidance there when needed.
- [ ] Add meaningful application tests with the first feature.
- [ ] Export and review this site's initial configuration with `lando drush cex -y`.
- [ ] Commit Composer and patch lock files; configure origin, push main/codex and enable branch protection.
- [ ] Provision dev/test/prod hosting and independent database/settings/secrets.
- [ ] Configure GitHub environments, verified SSH host keys, deployment variables and production approval rules.
- [ ] Run the first deployment against an empty database, then remove INITIAL_INSTALL.
- [ ] Configure cron, queue workers, backup retention and restore checks on hosting.
- [ ] Add a theme build workflow if the project introduces compiled frontend assets.
- [ ] Evaluate Config Split only if environment-specific exports are needed.
