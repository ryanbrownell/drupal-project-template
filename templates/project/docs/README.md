# 📚 Custom module documentation

Keep documentation for custom modules in this project-root `docs/` directory. Create a directory using each module's machine name when implementing the module, and add a link to its README here. No custom modules are included in a blank project.

## 🗂️ Directory layout

```text
docs/
  README.md                    # Module index and documentation conventions
  <module_name>/
    README.md                  # Current module behavior and service inventory
    AGENTS.md                  # Module-specific guidance, when needed
```

Module code stays in `web/modules/custom/<module_name>/`. Module READMEs and agent guidance belong here under `docs/<module_name>/`; do not place them under `web/`.

## 📝 Module READMEs

Read the module's README and any module-specific AGENTS.md before working on it. Create documentation with the first implementation and keep it current in the same change as the module's behavior.

Document current features, flows, access, APIs and data contracts. Include durable operational details such as security, cacheability, performance and migration requirements when they matter. Keep a concise inventory of every service defined by the module, with its service ID, purpose and behavior, so other modules can reuse it.

Use a fitting emoji prefix on every module README heading. Describe the current system; keep commit history, individual update hook IDs, one-off fixes, removed patterns and transient styling changes out of the README unless operationally critical.

## 🤖 Module agent guidance

Use `docs/<module_name>/AGENTS.md` for module-specific rules and important implementation constraints. Follow the root AGENTS.md for shared commit-message, documentation and release-note guidance. Keep shared rules in the root file and module-specific details alongside the module README.

## 📖 Module index

Add a link to each module's `docs/<module_name>/README.md` when its documentation is created.
