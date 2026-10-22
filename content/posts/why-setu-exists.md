---
title: Why Setu exists, and a simpler way of self-hosting compiled apps
seo_title: Self-hosting compiled apps, and why Setu exists | Setu
seo_description: Self-hosting compiled apps means wiring a proxy, TLS, a database, backups and updates by hand. Here is why we built Setu to do that part for you.
keyphrase: self-hosting compiled apps
excerpt: Rust and Go apps ship as one binary, yet running them on your own server still means a lot of glue. Setu is the control panel we built to handle that glue.
category: News
tags: setu, self-hosting, rust, go, control panel
cover_kicker: Why we built it
cover_alt: The Setu panel's site list on a single VPS, with each site's status and domain
---
Self-hosting compiled apps should be easy: a Rust or Go web app is one executable that you copy to a server and run. In practice, the binary is the smallest part of the job. You still need a domain, a certificate, a database, a service unit, backups, a way to update without breaking things, and some limit on how much memory each app may take.

Setu is an open-source control panel that does that part. This post explains the gap it fills and the choices behind it.

## The glue around self-hosting compiled apps

Take a typical small app: a Rust service that reads a database URL and a bind address from the environment. To put it on a VPS by hand, you would:

- create a system user and a directory layout for it;
- install PostgreSQL, create a role and a database, and keep the password somewhere safe;
- write a systemd unit, with hardening options if you remember them;
- put a reverse proxy in front and get a certificate for the domain;
- set up a nightly `pg_dump` and decide how long to keep the dumps;
- work out how to update it, and what to do when the new version does not start.

None of this is hard. All of it is repetitive, and the second and third app are no easier than the first. Hosting panels such as cPanel solved this problem for PHP sites years ago. For compiled apps there was no equivalent that stays close to the operating system, so we built one.

## What Setu does

Setu gives each site a domain, automatic HTTPS, its own PostgreSQL database, nightly backups, health-checked updates and resource limits, on servers you own. The app stays a published binary, and Setu runs it as a hardened systemd service.

![The Setu panel's Sites page listing several sites with their status](images/panel-sites.png "The Sites page: every site on every server, in one list.")

The only thing Setu knows about an app is its manifest, a small TOML file per version. It says where to download the release and its sha256, which executable to run, whether the app needs a database or persistent directories, how its environment is built and which path answers the health check. There is no per-language support in Setu itself. If it compiles to one executable, binds an address from the environment and answers a health check, Setu can run it. We make the case for this kind of app in [single-binary web apps are underrated](post:single-binary-web-apps).

## The choices behind it

A few decisions shape everything else.

**One binary for everything.** `setu` is the control plane, the per-server agent and the privileged helper, selected by subcommand. A release is one static musl archive per architecture, x86_64 and aarch64.

**systemd instead of a container runtime.** Every site runs as `setu-site@<id>.service` under its own user, with memory and CPU limits enforced by cgroups. You can debug it with `systemctl` and `journalctl`, like anything else on the box.

**A small root surface.** The agent is not root. It reaches root only through `setu helper <verb> --site <id>`, with typed JSON on stdin and no paths, modes or owners from the caller. The whole sudoers file is two lines:

```text
setu ALL=(root) NOPASSWD: /opt/setu/setu helper *
setu ALL=(postgres) NOPASSWD: /usr/bin/psql, /usr/bin/pg_dump, /usr/bin/pg_restore
```

**Updates that roll back.** An update backs up first. If the new version does not come up healthy, Setu puts the old binary and env back and, when the new version already ran, restores the database and data directories too.

**The control plane never SSHes.** Agents long-poll it over HTTPS, outbound only, and every command is typed and idempotent, so a retry is always safe.

## What Setu is not

Setu is early, and some things are left out on purpose. Containers as a runtime are planned for phase 2; the manifest already carries `run.kind = "image"`, but it is refused at provisioning for now. Backups stay on the server in this phase; copying them off the box is your job until off-box backups land. Disk use is reported, not enforced. Managed interpreted runtimes (PHP, Node, Python) are out of scope; apps that need an interpreter will ship as an image.

Expect rough edges and breaking changes before 1.0. The plan for later phases is on the [roadmap](https://setucp.com/docs/roadmap).

## Running on itself

The first app in Setu's catalogue is Vyasa, a CMS written in Rust that ships as one server binary plus PostgreSQL. This site is that setup: setucp.com and its docs are a Vyasa site, run by the Setu panel at panel.setucp.com, on one VPS. If something in Setu breaks, we feel it first.

The current releases are Setu 0.1.5 and Vyasa 0.3.3. Setu supports Ubuntu 22.04, 24.04 and 26.04 and Debian 12 and 13, on x86_64 and aarch64. It is licensed under AGPL-3.0 and the code is on [GitHub](https://github.com/setucp/setu).

## Next steps

If you have a VPS and a DNS name, [install Setu in five minutes](post:install-setu-in-five-minutes), then put [your first Vyasa site on it](post:first-vyasa-site-on-setu). The full install reference is at [setucp.com/docs/install](https://setucp.com/docs/install).
