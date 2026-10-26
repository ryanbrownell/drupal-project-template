# Environment examples

These files contain examples only. Copy local overrides to the project root and keep real credentials in ignored files. Copy server settings directly to the server's shared directory and edit them there.

- `.lando.local.yml`: local Xdebug and optional isolated test database service.
- `dev.local.env`: local environment overrides.
- `self.site.yml.example`: workstation SSH aliases; adapt into `.lando/drush/self.site.yml`.
- `server.settings.local.php`: server database, hash salt and trusted hosts.
- `server.secrets.php`: private integration overrides.

The root README documents the hosting layout and GitHub environment variables. Hosting credentials are never generated or uploaded by the project generator.
