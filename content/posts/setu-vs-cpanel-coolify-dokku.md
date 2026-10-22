---
title: Looking for a cPanel alternative? Setu vs Coolify and Dokku
seo_title: cPanel alternative for compiled apps? Setu vs Coolify, Dokku
seo_description: Looking for a cPanel alternative for Rust or Go apps? A fair comparison of Setu, cPanel, Coolify and Dokku, and the kind of workload each one fits best.
keyphrase: cPanel alternative
excerpt: cPanel, Coolify, Dokku and Setu solve different problems. A fair look at what each is built around, so you can pick the one that fits your apps.
category: Ecosystem
tags: comparison, cpanel, coolify, dokku, self-hosting
cover_kicker: Fair comparison
cover_alt: The Setu panel's site overview next to a list of other hosting tools
---
If you run Rust or Go services on your own VPS and want a cPanel alternative, you will quickly find three well-known names: cPanel itself, Coolify and Dokku. They are good tools, and they are built around different kinds of app. This post compares them with Setu on the things that decide which one fits, and says plainly where Setu is not the right choice.

## Four tools, four starting points

The quickest way to tell them apart is to ask what each one assumes an app is.

- **cPanel** (with WHM) is a commercial, licensed panel built for traditional web hosting: PHP sites, email accounts, DNS zones, FTP, databases. It is widely used by shared hosting providers.
- **Coolify** is an open-source, self-hostable platform that deploys apps from Git repositories, Dockerfiles or Docker Compose files, and runs them as containers, with a web UI.
- **Dokku** is an open-source, Docker-powered platform in the style of Heroku: you `git push` to the server, it builds the app with buildpacks or a Dockerfile, and you manage it from the command line, with plugins for databases and certificates.
- **Setu** is an open-source (AGPL-3.0) control panel for apps that ship as one compiled binary. It downloads a published release, verifies its checksum, and runs it as a hardened systemd service. No build step and no container runtime.

## Side by side

| | cPanel | Coolify | Dokku | Setu |
|---|---|---|---|---|
| Built around | PHP sites and shared hosting | containers from Git or images | containers from `git push` | published single binaries |
| Runtime | web server with PHP | Docker | Docker | systemd, one unit per site |
| Builds on the server | no | yes, from source | yes, from source | no, it installs releases |
| Interface | web UI | web UI | CLI | web UI and REST API |
| Licence | commercial | open source | open source | AGPL-3.0 |

The table covers well-known, stable traits only. Each tool has far more features than fit in a row.

## Where Setu differs as a cPanel alternative

**It installs releases rather than building code.** Setu reads a manifest per app version: the release URL, its sha256, the executable, what the app needs and how its environment is built. The agent checks the checksum, and the root helper checks it again before installing. If your apps already publish release binaries, there is nothing to build on the server and no image to maintain.

**It runs sites as plain systemd units.** Every site is `setu-site@<short>.service` under its own user, with `MemoryMax=` and `CPUQuota=` from its plan. You debug it with `systemctl` and `journalctl`. There is no container layer between you and the process.

**It includes the database and the safety net.** Each site gets its own PostgreSQL database and role, created at provisioning and passed to the app through its environment. Nightly backups of the database and declared directories are built in, and so is restore from the panel. An update backs up first and, if the new version fails its health check, rolls back, restoring the database when the new version already ran.

![The Setu site overview with status, app version, memory, disk and port](images/panel-site.png "A site in Setu: one systemd service, one database, one route.")

## Where the others fit better

This part matters as much as the rest.

- **You host PHP sites, email and DNS for customers.** That is cPanel's home ground. Setu does not manage mail, DNS zones or PHP, and will not.
- **You want to deploy from a Git repository.** Coolify and Dokku build your code on the server. Setu expects a published binary; building from source is only an idea on its roadmap for a later phase.
- **Your apps need containers today.** Coolify and Dokku run images now. Setu accepts `run.kind = "image"` in a manifest, but refuses it at provisioning until phase 2 adds rootless Podman.
- **You need a mature tool.** Setu is early. Expect rough edges and breaking changes before 1.0. Off-box backups, enforced disk quotas and two-factor sign-in are still on the roadmap.

## How to choose

Ask three questions.

1. **What does your app look like when it ships?** A PHP site points to cPanel. A Dockerfile or a repository points to Coolify or Dokku. A release binary points to Setu.
2. **Do you want a build step on your server?** If yes, the container platforms give you one. If you would rather your server only run verified artefacts, Setu is built for that.
3. **How close do you want to be to the operating system?** Setu keeps everything as systemd units, a Postgres instance and Caddy routes you can inspect directly.

It is also fine to use more than one. Setu manages only its own nftables table and its own Caddy routes, and leaves other tables and routes alone, but its installer expects a fresh server and sets up PostgreSQL and Caddy itself. Give it its own VPS rather than sharing one with another panel.

## Next steps

If your apps are compiled, try it on a spare VPS: [install Setu in five minutes](post:install-setu-in-five-minutes). For the design reasoning behind these trade-offs, read [what a control panel should do](post:what-a-control-panel-should-do) and [why single-binary web apps are underrated](post:single-binary-web-apps). The full feature scope and what is coming next are on the [roadmap](https://setucp.com/docs/roadmap).
