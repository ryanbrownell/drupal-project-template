# Drupal project generator

This repository contains a generator, not an installed Drupal site. Source templates live in `templates/project/`; files ending in `.tpl` are rendered by `scripts/create_project.py`. Generated projects must work independently of this repository and both source projects.

- Keep the CLI dependent only on Python 3.9+ standard library and Bash. Run PHP/Composer/Drush through Lando when exercising real generated projects; do not require host PHP.
- Never copy source-project credentials, Drupal code, config exports, application patches or dependencies into the template.
- Refuse nonempty destinations and keep setup rerunnable. Avoid shell interpolation of user input.
- Preserve first-start ordering: Lando must start before Drupal or vendor dependencies exist. Never add unconditional Composer/Drush build steps that prevent that bootstrap.
- Commit manifests and patch locks in generated projects; do not store downloaded Drupal/vendor trees in this repository.
- Keep deployment targets configurable and opt-in. Test remote behavior with isolated stubs; do not publish or deploy during generator validation.
- Run `python3 -m unittest discover -s tests -v` after behavioral changes. Parse rendered JSON/XML/YAML and check shell syntax when templates change.
- Maintain the source review and limitations in README.md, and keep generated README/AGENTS/TODO aligned with implemented behavior.
- Preserve the source projects' generic commit-message, documentation and release-note guidelines in generated AGENTS.md. Generated custom module READMEs and agent guidance belong in project-root `docs/<module_name>/`, indexed by `docs/README.md`.
- Provide concise commit messages when requested and explain non-obvious decisions in comments and commit notes. Agents do not push; the user handles all pushes.
