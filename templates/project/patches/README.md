# Composer patches

Composer Patches 2.x reads the root `patches.json`. The template includes no patches from another site. Store reviewed patch files in this directory, grouped by package when useful, and define them using paths relative to the Composer root.

For each patch, record its purpose, upstream issue, affected versions and removal condition here. Use expanded definitions when setting an explicit checksum or depth:

```json
{
    "patches": {
        "vendor/package": [{
            "description": "Issue reference and reason",
            "url": "patches/package/fix.patch",
            "depth": 1
        }]
    }
}
```

After intentionally adding/changing a patch:

```bash
lando composer patches-relock
lando composer patches-repatch
lando composer validate --strict
```

Review and commit `patches.json`, the patch files, `patches.lock.json`, and relevant Composer manifest/lock changes. Updating `patches.json` alone does not apply a patch to an already installed package. Remove patches after verifying the upstream release includes the fix. Prefer committed local patch files over mutable PR/MR patch URLs.

See the [Composer Patches documentation](https://docs.cweagans.net/composer-patches/usage/recommended-workflows/).
