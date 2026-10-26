name: Reusable Drupal deployment

on:
  workflow_call:
    inputs:
      environment:
        type: string
        required: true
      ref:
        type: string
        required: true

permissions:
  contents: read

jobs:
  quality:
    if: ${{ vars.DEPLOY_ENABLED == 'true' }}
    uses: ./.github/workflows/quality.yml
    with:
      ref: ${{ inputs.environment == 'dev' && inputs.ref || format('refs/tags/{0}', inputs.ref) }}
  deploy:
    needs: quality
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    concurrency:
      group: deploy-${{ inputs.environment }}
      cancel-in-progress: false
    env:
      DEPLOY_ENVIRONMENT: ${{ inputs.environment }}
      DEPLOY_REF: ${{ inputs.ref }}
      SSH_HOST: ${{ vars.SSH_HOST }}
      SSH_USER: ${{ vars.SSH_USER }}
      SSH_PORT: ${{ vars.SSH_PORT || '22' }}
      DEPLOY_ROOT: ${{ vars.DEPLOY_ROOT }}
      SITE_URI: ${{ vars.SITE_URI }}
      INITIAL_INSTALL: ${{ vars.INITIAL_INSTALL || 'false' }}
    steps:
      - uses: actions/checkout@v6
        with:
          ref: ${{ inputs.environment == 'dev' && inputs.ref || format('refs/tags/{0}', inputs.ref) }}
          fetch-depth: 0
          persist-credentials: false
      - name: Validate release reference
        shell: bash
        run: |
          set -euo pipefail
          case "$DEPLOY_ENVIRONMENT" in
            dev) ;;
            test|prod)
              [[ "$DEPLOY_REF" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
              [[ "$(git rev-parse HEAD)" == "$(git rev-parse "refs/tags/$DEPLOY_REF^{commit}")" ]]
              ;;
            *) exit 2 ;;
          esac
          git merge-base --is-ancestor HEAD origin/main
      - name: Set up PHP
        uses: shivammathur/setup-php@v2
        with:
          php-version: '@@PHP_VERSION@@'
          extensions: gd, pdo_mysql, intl, mbstring, zip
          tools: composer:v2
          coverage: none
      - name: Build deployment artifact from composer.lock
        run: |
          composer validate --strict --check-lock
          composer install --no-dev --prefer-dist --no-interaction --no-progress --optimize-autoloader
          php scripts/prepare-settings.php deploy
      - name: Configure SSH
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          SSH_KNOWN_HOSTS: ${{ secrets.SSH_KNOWN_HOSTS }}
        run: |
          set -euo pipefail
          test -n "$SSH_PRIVATE_KEY"
          test -n "$SSH_KNOWN_HOSTS"
          install -d -m 700 ~/.ssh
          printf '%s\n' "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519
          printf '%s\n' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts
          chmod 600 ~/.ssh/id_ed25519 ~/.ssh/known_hosts
      - name: Upload, back up, and deploy
        run: bash scripts/deploy.sh
      - name: Remove SSH credentials
        if: always()
        run: rm -f ~/.ssh/id_ed25519 ~/.ssh/known_hosts
