{
    "name": "project/@@MACHINE_NAME@@",
    "description": "Composer-managed Drupal project",
    "type": "project",
    "license": "GPL-2.0-or-later",
    "repositories": [{"type": "composer", "url": "https://packages.drupal.org/8"}],
    "require": {
        "composer/installers": "^2.3",
        "cweagans/composer-patches": "^2.0",
        "drupal/core-composer-scaffold": "*",
        "drupal/core-recommended": "*",
        "drush/drush": "^13"
    },
    "require-dev": {
        "dealerdirect/phpcodesniffer-composer-installer": "^1.1",
        "drupal/coder": "^8.3",
        "drupal/core-dev": "*",
        "mglaman/phpstan-drupal": "^2.0",
        "phpstan/phpstan": "^2.0"
    },
    "conflict": {"drupal/drupal": "*"},
    "minimum-stability": "stable",
    "prefer-stable": true,
    "config": {
        "allow-plugins": {
            "composer/installers": true,
            "cweagans/composer-patches": true,
            "dealerdirect/phpcodesniffer-composer-installer": true,
            "drupal/core-composer-scaffold": true,
            "drupal/core-project-message": true,
            "drupal/core-recipe-unpack": true,
            "php-http/discovery": true,
            "phpstan/extension-installer": false,
            "symfony/runtime": true
        },
        "platform": {"php": "@@PHP_VERSION@@.0"},
        "sort-packages": true,
        "optimize-autoloader": true
    },
    "extra": {
        "drupal-scaffold": {
            "locations": {"web-root": "web/"},
            "file-mapping": {"[web-root]/example.gitignore": false}
        },
        "installer-paths": {
            "web/core": ["type:drupal-core"],
            "web/libraries/{$name}": ["type:drupal-library"],
            "web/modules/contrib/{$name}": ["type:drupal-module"],
            "web/themes/contrib/{$name}": ["type:drupal-theme"],
            "web/profiles/contrib/{$name}": ["type:drupal-profile"],
            "web/modules/custom/{$name}": ["type:drupal-custom-module"],
            "web/themes/custom/{$name}": ["type:drupal-custom-theme"],
            "web/profiles/custom/{$name}": ["type:drupal-custom-profile"],
            "drush/Commands/contrib/{$name}": ["type:drupal-drush"],
            "recipes/{$name}": ["type:drupal-recipe"]
        },
        "patches-file": "patches.json"
    },
    "scripts": {
        "lint": "@php scripts/quality.php lint",
        "lint:fix": "@php scripts/quality.php lint:fix",
        "phpstan": "@php scripts/quality.php phpstan",
        "test": "@php scripts/quality.php test",
        "test:kernel": "@php scripts/quality.php test:kernel",
        "test:functional": "@php scripts/quality.php test:functional",
        "test:js": "@php scripts/quality.php test:js",
        "quality": ["@lint", "@phpstan", "@test"],
        "post-install-cmd": ["@php scripts/prepare-settings.php auto"],
        "post-update-cmd": ["@php scripts/prepare-settings.php auto"]
    }
}
