#!/usr/bin/env python3
"""Render a standalone Drupal workspace, then bootstrap it through Lando."""

import argparse
import json
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "project"
TOKEN = re.compile(r"@@([A-Z_]+)@@")


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value if value and value[0].isalpha() else "site-" + (value or "drupal")


def prompt(label, default):
    return input(f"{label} [{default}]: ").strip() or str(default)


def php_string(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def normalize_url(value):
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.port
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("The local URL must be an http(s) hostname without a port or path.")
    host = parsed.hostname.lower()
    if len(host) > 253 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        raise ValueError("The local URL must contain a valid DNS hostname.")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
           for label in host.split(".")):
        raise ValueError("The local URL contains an invalid DNS label.")
    return f"{parsed.scheme}://{host}", host


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", help="New or empty project directory")
    parser.add_argument("--yes", "-y", action="store_true", help="Accept defaults without prompts")
    parser.add_argument("--site-name", help="Human-readable Drupal site name")
    parser.add_argument("--machine-name", help="Lando name and Composer project slug")
    parser.add_argument("--url", help="Local URL, e.g. https://example.lndo.site")
    parser.add_argument("--php", choices=("8.3", "8.4"), help="PHP runtime (default: 8.4)")
    parser.add_argument("--database-port", type=int, help="Host DB port; 0 assigns a free port")
    parser.add_argument("--profile", choices=("minimal", "standard"), help="Core install profile")
    parser.add_argument("--admin-name", help="Local administrator username")
    parser.add_argument("--email", help="Site and administrator email")
    parser.add_argument("--timezone", help="IANA site timezone (default: UTC)")
    parser.add_argument("--locale", default="en", help="Installation language (default: en)")
    parser.add_argument("--drupal-version", default="", help="Optional stable constraint, e.g. ^11")
    parser.add_argument("--git-remote", default="", help="Optional origin URL; never contacted")
    parser.add_argument("--no-git", action="store_true", help="Do not initialize a local repository")
    parser.add_argument("--scaffold-only", action="store_true", help="Write files without running Lando")
    parser.add_argument("--no-install", action="store_true", help="Fetch dependencies but leave DB uninstalled")
    args = parser.parse_args(argv)
    interactive = not args.yes
    if interactive and not sys.stdin.isatty():
        parser.error("Use --yes for non-interactive generation.")

    name_default = Path(args.destination).name.replace("-", " ").title() if args.destination else "My Drupal Site"
    args.site_name = args.site_name or (prompt("Site name", name_default) if interactive else name_default)
    machine_default = slugify(Path(args.destination).name if args.destination else args.site_name)
    args.machine_name = args.machine_name or (prompt("Lando machine name", machine_default) if interactive else machine_default)
    args.destination = args.destination or (prompt("Project directory", "../" + args.machine_name) if interactive else "../" + args.machine_name)
    args.url = args.url or (prompt("Local URL", f"https://{args.machine_name}.lndo.site") if interactive else f"https://{args.machine_name}.lndo.site")
    args.php = args.php or (prompt("PHP version (8.3 or 8.4)", "8.4") if interactive else "8.4")
    if args.database_port is None:
        try:
            args.database_port = int(prompt("Host database port (0 = automatic)", "0")) if interactive else 0
        except ValueError:
            parser.error("Database port must be an integer.")
    args.profile = args.profile or (prompt("Install profile (minimal or standard)", "minimal") if interactive else "minimal")
    args.admin_name = args.admin_name or (prompt("Local administrator username", "admin") if interactive else "admin")
    args.email = args.email or (prompt("Site / administrator email", f"admin@{args.machine_name}.test") if interactive else f"admin@{args.machine_name}.test")
    args.timezone = args.timezone or (prompt("Site timezone", "UTC") if interactive else "UTC")
    if interactive and not args.git_remote and not args.no_git:
        args.git_remote = input("Git origin URL (optional; Enter to skip): ").strip()
    try:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.machine_name) or args.machine_name.endswith("-"):
            raise ValueError("Machine name must start with a letter and contain up to 40 lowercase letters, digits or hyphens.")
        if args.php not in ("8.3", "8.4") or args.profile not in ("minimal", "standard"):
            raise ValueError("Choose PHP 8.3 or 8.4 and the minimal or standard profile.")
        if args.database_port != 0 and not 1024 <= args.database_port <= 65535:
            raise ValueError("Database port must be 0 or between 1024 and 65535.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", args.email):
            raise ValueError("Provide a valid site email address.")
        for value in (args.site_name, args.admin_name, args.email, args.git_remote):
            if any(ord(char) < 32 or ord(char) == 127 for char in value) or "@@" in value:
                raise ValueError("Names and URLs cannot contain control characters or template tokens.")
        if not 1 <= len(args.site_name) <= 255 or not 1 <= len(args.admin_name) <= 60:
            raise ValueError("Site names must be 1–255 characters; administrator names 1–60 characters.")
        if args.drupal_version and not re.fullmatch(r"[~^]?[0-9]+(?:\.[0-9x*]+){0,2}", args.drupal_version):
            raise ValueError("Use a stable Drupal constraint such as ^11, ~11.4.0 or 11.4.*.")
        if not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z0-9]+)*", args.locale):
            raise ValueError("Invalid Drupal language code.")
        ZoneInfo(args.timezone)
        args.url, args.host = normalize_url(args.url)
        if args.git_remote.startswith("-") or (args.no_git and args.git_remote):
            raise ValueError("A Git remote requires Git initialization and cannot start with '-'.")
    except (ValueError, ZoneInfoNotFoundError) as error:
        parser.error(str(error))
    return args


def render_project(args):
    destination = Path(args.destination).expanduser().absolute()
    if destination.is_symlink():
        raise ValueError("The destination cannot be a symbolic link.")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f"Destination must be new or completely empty: {destination}")
    if not args.scaffold_only and not shutil.which("lando"):
        raise ValueError("Lando is required. Install it or use --scaffold-only.")
    if not args.no_git and not shutil.which("git"):
        raise ValueError("Git is required unless --no-git is supplied.")
    project = {
        "schema_version": 1,
        "site_name": args.site_name,
        "machine_name": args.machine_name,
        "url": args.url,
        "php": args.php,
        "profile": args.profile,
        "admin_name": args.admin_name,
        "email": args.email,
        "timezone": args.timezone,
        "locale": args.locale,
        "drupal_version": args.drupal_version,
    }
    variables = {
        "PROJECT_JSON": json.dumps(project, indent=2, ensure_ascii=False),
        "SITE_NAME": args.site_name.replace("`", "'"),
        "MACHINE_NAME": args.machine_name,
        "LOCAL_URL": args.url,
        "LOCAL_URL_JSON": json.dumps(args.url),
        "LOCAL_HOST_JSON": json.dumps(args.host),
        "TRUSTED_HOST_PHP": php_string("^" + re.escape(args.host) + "$"),
        "PHP_VERSION": args.php,
        "DB_PORT": str(args.database_port) if args.database_port else "true",
    }
    # Validate and render everything in memory before creating the destination.
    rendered = []
    for source in sorted(TEMPLATE_ROOT.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(TEMPLATE_ROOT)
        target = relative.with_suffix("") if source.suffix == ".tpl" else relative
        content = source.read_text()
        if source.suffix == ".tpl":
            content = TOKEN.sub(lambda match: variables[match[1]], content)
        rendered.append((target, content, source.stat().st_mode & 0o777))
    destination.mkdir(parents=True, exist_ok=True)
    for relative, content, mode in rendered:
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(mode | (0o111 if path.suffix == ".sh" else 0))
    if not args.no_git:
        subprocess.run(["git", "init", "--initial-branch=main", str(destination)], check=True)
        if args.git_remote:
            subprocess.run(["git", "-C", str(destination), "remote", "add", "origin", args.git_remote], check=True)
    return destination


def main():
    args = parse_args()
    try:
        destination = render_project(args)
        print(f"\nProject created: {destination}", flush=True)
        if args.scaffold_only:
            print(f"Run: cd {shlex.quote(str(destination))} && ./scripts/setup.sh")
        else:
            command = [sys.executable, str(destination / "scripts/setup-project.py")]
            if args.no_install:
                command.append("--no-install")
            subprocess.run(command, cwd=destination, check=True)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
