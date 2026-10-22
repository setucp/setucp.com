---
title: The Setu trust model, explained in plain words
seo_title: The Setu trust model, who is root and why | Setu
seo_description: The Setu trust model explained, covering which part runs as root, what the helper refuses, what hosted sites can reach, and what you must protect.
keyphrase: Setu trust model
excerpt: A control panel runs other people's binaries as root-managed services. Here is exactly which part of Setu is trusted, what it can do, and what it cannot.
category: Engineering
tags: security, trust, sudo, isolation, systemd
cover_kicker: Security model
cover_alt: Cover card for the post The Setu trust model, explained in plain words
---
Any control panel that creates users, writes systemd units and installs binaries needs root somewhere. The question worth asking is not whether it has root, but which part, for what, and under whose control. The Setu trust model answers that in a page of plain words; this post goes through it and explains the reasoning.

## Four components, four levels of trust

Setu is one binary, `setu`, that plays different roles by subcommand. Each role runs with different rights:

| Component | Runs as | Can |
|---|---|---|
| `setu serve`, the control plane | user `setu` on the panel box | decide what should exist: sites, databases, routes, backups |
| `setu agent`, one per server | user `setu`, no root | carry out the control plane's commands by asking the helper, program Caddy through a socket, run `psql` as `postgres` |
| `setu helper`, same binary | root, only through `sudo -n` | nine fixed verbs |
| a hosted site | its own user `setu-site-<id>` | read and write its own `data/` and `run/`, bind its loopback port |

The control plane never SSHes into servers. It queues typed, idempotent commands, and agents long-poll for them over outbound HTTPS with a per-server token. Nothing connects in to an agent.

## The honest summary of the Setu trust model

The docs put it in one sentence: **whoever controls the control plane controls every joined server, at root, within the helper's verbs.**

That is the same trust any control plane asks for. If someone owns your panel host, its database, its `secret_key`, or an `owner` or `operator` account, they can create users, write units and env files, install binaries and drop databases on every server that joined it.

What Setu adds is a bound on *what* root can be asked to do, not on *who* asks. A bug in the agent, or a compromised agent process, cannot become "run anything as root", because the only path to root is a short list of typed verbs. So protect the control plane the way you would protect a root SSH key.

One detail for single-box installs: when the panel and the agent share a machine, both run as the same `setu` user, so a compromise of either is a compromise of both.

## Root is a two-line sudoers file

The entire privileged surface is this file, `/etc/sudoers.d/setu`:

```text
setu ALL=(root) NOPASSWD: /opt/setu/setu helper *
setu ALL=(postgres) NOPASSWD: /usr/bin/psql, /usr/bin/pg_dump, /usr/bin/pg_restore
```

`helper *` looks broad, and it is safe only because the verbs take no free-form arguments. Each verb accepts a validated eight-character site id on the command line and typed JSON on standard input. It never accepts a path, a mode or an owner. It derives every path from the id, walks directories without following symlinks, and refuses whole archives that contain anything suspicious.

The second line is the one the docs flag openly: `psql` as `postgres` is a database superuser. Setu passes it scripts on standard input and only for names matching `site_<id>`, but this is the one place where more than Setu intended could happen. The helper itself is the subject of [Inside the privileged helper](post:privileged-helper-design).

## Sites are untrusted

Setu assumes the apps it runs may be hostile. Each site:

- runs as its own user, under a unit with `ProtectSystem=strict`, `NoNewPrivileges=yes`, `PrivateTmp` and cgroup limits;
- can write only `data/` and `run/`, never anything a privileged path later reads;
- cannot reach Caddy's admin API, which listens on a unix socket owned by group `caddy` with TCP 2019 off;
- cannot be reached from outside on its port, because nftables drops inbound 20000–29999 on every interface except loopback;
- cannot connect to another site's database, because every database revokes `CONNECT` from `PUBLIC`.

### What sites still share

The trust model is explicit about its limits. Sites on one server share the kernel, the Postgres instance and loopback. A site can reach a neighbour's port on 127.0.0.1, and an app that trusts `X-Forwarded-For` from 127.0.0.1 can be fooled by a neighbour about the client IP. This release is process isolation, not VM isolation. If you host tenants who do not trust each other, put them on separate servers. Containers are on the roadmap for those who need more.

## Secrets and operators

Database passwords and generated secrets are sealed with ChaCha20-Poly1305 under the panel's key before they are stored. They are never written to logs, never passed on a command line, and blanked out of the command queue once a command finishes. Operators see masked values; a reveal needs the operator's own password and is audited every time. Viewers never see a secret.

There is one thing Setu cannot promise: application logs are returned as the app wrote them. An app that prints its own secrets exposes them to operators. More on that in [Environment variables and secrets in Setu](post:env-variables-and-secrets).

## How the model is checked

Every release runs an end-to-end test on a real systemd in a container. It covers provisioning, the firewall, Caddy's admin port being closed, limits, backup and restore, an update that fails health and must roll back with the database restored, an agent killed mid-command, a reboot, and a lost Caddy config repaired. On a live server, `setu agent doctor` checks the parts of the model you can verify yourself:

```bash
setu agent doctor
```

It checks the helper binary's owner and mode, the sudoers file with `visudo -cf`, the nftables table, that nothing listens on `127.0.0.1:2019`, and more, and exits 1 on any failure.

## Next steps

Read the full [trust model](https://setucp.com/docs/trust) and the [security reference](https://setucp.com/docs/security), then [Checksums and signed releases](post:checksums-and-signed-releases) for how Setu verifies what it installs. Vulnerabilities go through GitHub's private reporting on [the repository](https://github.com/setucp/setu).
