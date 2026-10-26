#!/usr/bin/env python3
"""Install this workspace using Lando; safe to rerun after a failed setup."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".project-setup.json"


def run(*command):
    print("+ " + shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def merge(defaults, overrides):
    """Preserve upstream scaffolding and project-owned tooling together."""
    result = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def initialize_composer(project, state):
    current = json.loads((ROOT / "composer.json").read_text())
    if (ROOT / "composer.lock").exists() or state.get("upstream_initialized"):
        return
    if current["require"].get("drupal/core-recommended") != "*":
        return
    bootstrap = ROOT / ".drupal-bootstrap"
    if bootstrap.is_symlink() or (bootstrap.exists() and not state.get("bootstrap_owned")):
        raise ValueError("Refusing to replace an unrecognized .drupal-bootstrap directory.")
    if bootstrap.exists():
        shutil.rmtree(bootstrap)
    state["bootstrap_owned"] = True
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    package = "drupal/recommended-project"
    if project["drupal_version"]:
        package += ":" + project["drupal_version"]
    run("lando", "composer", "create-project", "--prefer-dist", "--no-install",
        "--no-scripts", "--no-interaction", "--stability=stable", package, ".drupal-bootstrap")
    upstream = json.loads((bootstrap / "composer.json").read_text())
    if "drupal/core-recommended" not in upstream.get("require", {}):
        raise ValueError("The downloaded project does not contain Drupal core-recommended.")
    manifest = merge(upstream, current)
    for name, constraint in upstream["require"].items():
        if name.startswith("drupal/core-") or name == "drupal/core":
            manifest["require"][name] = constraint
    manifest["require-dev"]["drupal/core-dev"] = upstream["require"]["drupal/core-recommended"]
    for source in bootstrap.rglob("*"):
        relative = source.relative_to(bootstrap)
        if relative.parts[0] in (".git", "vendor") or relative.name in ("composer.json", "composer.lock"):
            continue
        target = ROOT / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    temporary = ROOT / "composer.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")
    temporary.replace(ROOT / "composer.json")
    state["upstream_initialized"] = True
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    shutil.rmtree(bootstrap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-install", action="store_true", help="Leave the local database untouched")
    args = parser.parse_args()
    try:
        if not shutil.which("lando"):
            raise ValueError("Lando is required; no host PHP or Composer is needed.")
        project = json.loads((ROOT / "project.json").read_text())
        state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
        local_env = ROOT / "dev.local.env"
        if not local_env.exists():
            local_env.write_text("# Local overrides; ignored by Git.\n")
        run("lando", "start")
        initialize_composer(project, state)
        run("lando", "composer", "install", "--prefer-dist", "--no-interaction")
        if not (ROOT / "patches.lock.json").exists():
            run("lando", "composer", "patches-relock", "--no-interaction")
        run("lando", "php", "scripts/prepare-settings.php", "local")
        run("lando", "composer", "validate", "--strict")
        if not args.no_install:
            run("lando", "install")
            run("lando", "drush", "status", "--fields=drupal-version,bootstrap,db-status,uri")
            run("lando", "drush", "user:login")
        print(f"\nWorkspace ready: {project['url']}")
        print("Configuration directories are empty. Export your own configuration when ready: lando drush cex -y")
        if args.no_install:
            print("The database was left untouched. Run lando install when ready.")
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Setup stopped: {error}\nFiles were preserved. Fix the cause and rerun ./scripts/setup.sh.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
