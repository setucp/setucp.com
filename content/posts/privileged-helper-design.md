---
title: Inside the privileged helper that does Setu's root work
seo_title: Privileged helper design, Setu's small root surface | Setu
seo_description: How the Setu privileged helper keeps root small, with nine typed verbs, no paths from the caller, no-follow walks and hostile archives refused.
keyphrase: privileged helper
excerpt: The agent is not root. Everything it needs root for goes through nine typed verbs of one helper. Here is how that helper is built and what it refuses.
category: Engineering
tags: security, sudo, rust, systemd, design
cover_kicker: Engineering notes
cover_alt: Cover card for the post Inside the privileged helper that does Setu's root work
---
A server agent has to do root things: create users, write systemd units, install binaries, restore backups. The common shortcut is to run the whole agent as root, which turns every agent bug into a root bug. Setu instead routes all root work through a privileged helper with a deliberately tiny interface, and this post explains how that helper is designed.

## Why the agent is not root

`setu-agent.service` runs as the unprivileged user `setu`. Its only path to root is one command shape:

```bash
sudo -n /opt/setu/setu helper <verb> --site <short>
```

Its only path to the database superuser is `psql`, `pg_dump` and `pg_restore` as `postgres`. Logs are read with `journalctl` as `setu`, through membership of the `systemd-journal` group, not through the helper.

The helper is not a separate program. It is the same `setu` binary, root:root mode 0755 in a root-owned directory, selected by the `helper` subcommand. `sudo -n` means it never prompts: if the rule does not match, the call fails.

The goal is stated in the [trust model](post:setu-trust-model): the helper bounds *what* root can be asked to do. A compromised agent process is limited to the same verbs as a healthy one.

## Nine verbs, nothing free-form

| verb | what root does |
|---|---|
| `site-create` | create user `setu-site-<short>` (uid 30000–39999, no shell) and the site tree with `data/`, `run/` and the declared dirs |
| `write-unit` | render the drop-in `setu-site@<short>.service.d/10-setu.conf` from a fixed template; `daemon-reload` when changed |
| `write-env` | write `/srv/setu/sites/<short>/env`, root:root 0600 |
| `install` | verify a downloaded archive or binary and install it to `bin/<version>/` |
| `switch-version` | atomically swap the `bin/current` symlink |
| `unit` | `start`, `stop`, `restart` or `show` the site's unit |
| `backup` | stream a `tar.zst` of the backed-up dirs to stdout |
| `restore` | with the unit inactive, unpack into staging, chown to the site user, swap into `data/` |
| `site-remove` | disable the unit, remove the drop-in, `userdel`, remove the tree |

That list is the entire root surface for sites. Installing system pieces (units, sudoers, the firewall, Caddy) is **not** a helper verb. It runs only as real root from `setu agent install`, `setu agent install-system` or `install.sh`, so sudo cannot reach it.

## What crosses sudo, and what never does

The helper's only command-line arguments are the verb and `--site`, validated as `^[a-z0-9]{8}$`. Everything else is one line of typed JSON on standard input: unknown fields are refused and the input is capped at 1 MiB. Archives stream over stdin and stdout.

No path, no mode and no owner ever crosses sudo. That single rule removes a whole class of bugs: a caller cannot ask the helper to write somewhere interesting, because the helper never takes "somewhere" as input.

The helper then re-validates every value it is given, even though the control plane and agent already did:

- `version` matches `^[0-9A-Za-z.+-]{1,64}$`;
- `exec` is relative `[A-Za-z0-9._-]` segments with no `..`;
- `args` and env values contain no control characters;
- dir names match `^[a-z][a-z0-9-]{0,31}$`, env names `^[A-Z][A-Z0-9_]*$`;
- a sha256 is 64 lowercase hex characters.

Unit values are systemd-escaped and env values use systemd's `EnvironmentFile=` quoting, so a value cannot break out of its line.

## Paths derived, links never followed

Every path the privileged helper touches derives from the short id. Under `/srv/setu/sites`, each directory component is opened `O_NOFOLLOW|O_DIRECTORY` step by step from the root, so a symlink planted by a site user is never followed. Files are written to a temporary file and renamed inside root-owned parents. No setuid, setgid or sticky bit is ever set.

Backups get the same care in the other direction. `backup` skips links and special files a site user planted in `data/`, and skips regular files the site user does not own or that have more than one hard link. `setu agent doctor` checks that `fs.protected_hardlinks` is `1`.

## Hostile archives are refused whole

`install` and `restore` extract into a root-owned staging directory. Any entry with `..`, an absolute name, a symlink, a hard link, a device file or a setuid, setgid or sticky bit refuses the **whole** operation and leaves nothing behind. Only a clean extraction is renamed to `bin/<version>/`.

For an install, the helper also re-hashes the download. The agent fetched the file to `/var/lib/setu/downloads/<sha256>.tar.gz` and verified it; the helper opens it with `O_NOFOLLOW`, requires a regular file, and checks the hash again against the manifest's `sha256`. With `format = "binary"`, it copies the file to `bin/<version>/<exec>`, mode 0755, root-owned, with no special bits whatever the download had.

### No test back doors in release builds

Tests need to run the helper against a fake filesystem root. That option, `--root <dir>`, exists only in builds with the `test-root` feature, is refused when `SUDO_UID` is set, and the release workflow fails if the published binary offers it.

The sudoers file is two lines, checked with `visudo -cf` before it is installed:

```text
setu ALL=(root) NOPASSWD: /opt/setu/setu helper *
setu ALL=(postgres) NOPASSWD: /usr/bin/psql, /usr/bin/pg_dump, /usr/bin/pg_restore
```

## Checking the privileged helper on your own server

You do not have to take any of this on faith. On any server, as root:

```bash
setu agent doctor
```

Its `helper` row checks that `/opt/setu/setu` is a regular file, root:root, mode exactly 0755, in a root-owned directory without group or other write. The `sudoers` row runs `visudo -cf /etc/sudoers.d/setu`. The `protected-hardlinks` row checks the sysctl.

## Next steps

The full verb table and validation rules are in the [security reference](https://setucp.com/docs/security), and the agent side is in the [agent docs](https://setucp.com/docs/agent). For how the helper's checksum check fits with the rest of Setu's verification, read [Checksums and signed releases](post:checksums-and-signed-releases).
