name: @@MACHINE_NAME@@
recipe: drupal11

config:
  webroot: web
  php: '@@PHP_VERSION@@'
  composer_version: '2-latest'
  database: mariadb:11.4
  xdebug: false

proxy:
  appserver:
    - @@LOCAL_HOST_JSON@@
  mailhog:
    - mail.@@MACHINE_NAME@@.lndo.site

env_file:
  - dev.defaults.env
  - dev.local.env

services:
  database:
    portforward: @@DB_PORT@@
  appserver:
    config:
      php: .lando/php/php.ini
    overrides:
      environment:
        DRUSH_OPTIONS_URI: @@LOCAL_URL_JSON@@
        PHP_IDE_CONFIG: serverName=appserver
        XDEBUG_MODE: debug,develop
      logging:
        options:
          max-file: '3'
          max-size: '10m'
    scanner:
      okCodes: [200, 302, 303, 400, 403, 500]
  node:
    type: node:24
  mailhog:
    type: mailhog
    hogfrom: [appserver]
    portforward: true
    overrides:
      image: anatomicjc/mailhog:1.0.1

# The first start must succeed before Composer has downloaded Drupal.
events:
  post-start:
    - appserver: 'if [ -f /app/vendor/autoload.php ]; then php /app/scripts/prepare-settings.php local; fi'

tooling:
  install:
    service: appserver
    description: Install a fresh local site; refuses an existing Drupal database.
    cmd: php /app/scripts/install-site.php
  drush:
    service: appserver
    cmd: /app/vendor/bin/drush --root=/app/web
  phpunit:
    service: appserver
    cmd: /app/vendor/bin/phpunit -c /app/phpunit.xml.dist
  phpcs:
    service: appserver
    cmd: /app/vendor/bin/phpcs --standard=/app/phpcs.xml.dist
  phpcbf:
    service: appserver
    cmd: /app/vendor/bin/phpcbf --standard=/app/phpcs.xml.dist
  phpstan:
    service: appserver
    cmd: /app/vendor/bin/phpstan analyse -c /app/phpstan.neon.dist
  npm:
    service: node
    cmd: npm
