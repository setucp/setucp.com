---
title: How to harden an Ubuntu server before you install Setu
seo_title: Harden an Ubuntu server for Setu: a checklist | Setu
seo_description: A practical checklist to harden an Ubuntu server for Setu: what Setu locks down for you, and the SSH, firewall, update and backup work that stays yours.
keyphrase: harden an Ubuntu server
excerpt: Setu locks down its own surface: site ports, Caddy's admin API, its sudoers file. SSH, the host firewall, updates and off-box copies are yours. A checklist for both.
category: Guides
tags: security, ubuntu, ssh, firewall, hardening
cover_kicker: Security guide
cover_alt: A checklist next to a terminal showing setu agent doctor passing on an Ubuntu server
---
A fresh VPS is reachable from the whole internet within a minute of booting, and the defaults are tuned for convenience. Before you install a control panel on it, it is worth taking an hour to harden an Ubuntu server properly. Setu does part of that work for you, and is explicit about the part it leaves alone.

## Start from a supported release

Setu 0.1.5 installs on Ubuntu 22.04, 24.04 and 26.04, and on Debian 12 and 13, on x86_64 and aarch64. Anything else is refused unless you force it. Pick a current LTS, use a fresh machine rather than one that already runs other services, and make sure ports 80 and 443 are reachable: Caddy needs both for automatic HTTPS.

The steps below use Ubuntu commands; Debian is the same with small differences (for example, `ufw` is not installed by default there).

## What Setu already hardens

It helps to know where the line is. The installer and `setu agent install` set up the following, and `setu agent doctor` checks most of it:

- **Site ports stay private.** Sites listen on ports 20000–29999. An nftables table, `inet setu`, drops inbound TCP to that range on every interface except loopback, so the only way in is through Caddy. The table is loaded by `setu-nftables.service`.
- **Caddy's admin API is not on the network.** Caddy is programmed only through a unix socket owned by group `caddy`; TCP port 2019 is off. Site users are not in that group.
- **Root is reached through a small door.** The agent runs as `setu`, not root. The sudoers file is exactly two lines: one for `setu helper` with typed verbs, one for `psql`, `pg_dump` and `pg_restore` as `postgres`.
- **Each site is its own user** under a hardened unit (`ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `NoNewPrivileges`, `RestrictSUIDSGID`), able to write only its `data/` and `run/` directories.
- **Databases are fenced.** Every site database revokes `CONNECT` from `PUBLIC`, so one site's role cannot connect to another's database.

The [trust model](post:setu-trust-model) explains why these lines are drawn where they are.

## What stays yours

The security docs say it in one sentence: Setu manages only its own nftables table, and SSH, Postgres and everything else on the host are yours to firewall. Here is a reasonable baseline.

### 1. Lock down SSH

Use key-based login and turn passwords off. Put your public key in `~/.ssh/authorized_keys` for a non-root admin user first, confirm you can log in with it, then set in `/etc/ssh/sshd_config` (or a file under `/etc/ssh/sshd_config.d/`):

```text
PasswordAuthentication no
PermitRootLogin prohibit-password
```

Then `systemctl reload ssh`. Keep your current session open until a new one works.

### 2. Add a host firewall

Setu's table only covers site ports. For everything else, a default-deny firewall that allows SSH, HTTP and HTTPS is a sensible start:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status verbose
```

Setu never runs `flush ruleset`; it adds and replaces only `table inet setu`, so rules that other tools manage stay intact. Do not open 20000–29999 and do not open PostgreSQL's port: on Ubuntu, Postgres listens on localhost by default, and Setu's sites reach it there.

### 3. Keep packages patched

Sites share the kernel with each other, so a kernel bug is everyone's bug. Install security updates automatically and reboot when the kernel changes:

```bash
apt install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

Setu units are enabled when a site starts, so sites come back on their own after a reboot. The end-to-end test reboots its box and checks that sites serve again.

### 4. Leave `fs.protected_hardlinks` on

Setu's backup refuses to follow links that a site user planted, and it relies on the kernel's hard-link protection. `setu agent doctor` checks it:

```bash
sysctl fs.protected_hardlinks    # should print 1, Ubuntu's default
```

## Protect the control plane like a root key

Whoever controls the control plane controls every server joined to it, at root, within the helper's verbs. On a single-box install the panel and the agent run as the same `setu` user. That makes a few files and accounts critical:

- `/etc/setu/setu.toml` (mode 0600) holds the database password and the `secret_key` that seals every site secret. Keep a copy off the box, stored like a private key, and nowhere public.
- `/etc/setu/agent.toml` (0600) holds the server token.
- Operator accounts: give people the lowest role that works. `viewer` never sees a secret; `operator` can do everything except manage operators and plans. The login limiter allows 10 failures per IP per 15 minutes. Two-factor sign-in is not in 0.1.x (it is planned for 0.2), so use long, unique passwords and keep the number of owners small.

## Get backups off the machine

Hardening is also about recovering. In 0.1.x, site backups live at `/var/lib/setu/backups/` on the same server and are **not encrypted** and **not copied off the box**. Copy them yourself, for example with a nightly job as root:

```bash
rsync -a /var/lib/setu/backups/ backup-host:setu/$(hostname)/
```

Treat the destination as sensitive: a database dump holds whatever the app stored. [How Setu backups work](post:how-setu-backups-work) covers the schedule and retention.

## Separate tenants who do not trust each other

Setu 0.1.x isolates sites by user, unit hardening and cgroup limits, not by virtual machine. Sites on one box share the kernel, the Postgres instance and loopback: a site can connect to another site's port on 127.0.0.1. If you host people who must not be able to affect each other, put them on separate servers. Network isolation between sites is on the roadmap.

## Check it, then next steps

After installing, run the doctor on each server:

```bash
setu agent doctor
```

It prints one row per check and exits 1 if any fails. Run `ss -tlnp` too, and make sure nothing you did not expect is listening on a public address.

- Read the [security model](https://setucp.com/docs/security) for the full list of what sites share.
- See how root access is bounded in [inside the privileged helper](post:privileged-helper-design).
- Ready? Follow the [install guide](https://setucp.com/install).
