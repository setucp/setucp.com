---
title: "The Setu roadmap: where Setu goes from 0.2 to 1.0"
seo_title: "Setu roadmap: containers, off-box backups, 1.0 | Setu"
seo_description: The Setu roadmap from 0.2 to 1.0: containers, encrypted off-box backups, site moves, Cloudflare tunnels, a hosted panel, a catalogue and billing.
keyphrase: Setu roadmap
excerpt: Setu 0.1.x runs single-binary apps on servers you own. Here is what comes next, release by release, from containers and off-box backups in 0.2 to the bar set for 1.0.
category: News
tags: roadmap, releases, containers, backups, plans
cover_kicker: Project news
cover_alt: A timeline of Setu releases from 0.1 to 1.0 with the main theme of each release
---
Setu 0.1.x does one thing: it runs single-binary web apps on servers you own, with a domain, TLS, a database, backups, updates and limits for each site. People who try it reasonably ask what comes next and in what order. This post walks through the Setu roadmap as it stands in the repository, release by release, and is clear about which parts are decided and which are still open.

One rule shapes all of it: each later phase gets its own spec and plan only when the one before it ships, because those plans must reference real code interfaces, not guessed ones. So the further out a release is, the less detail it has.

## Where the Setu roadmap starts: 0.1.x

0.1.0 was the MVP. The 0.1 releases since then added follow-ups and reach rather than new architecture:

| Release | What it added |
|---|---|
| 0.1.1 | raw single-binary downloads (`format = "binary"`), nightly panel self-backup, server token rotation, operator deletion |
| 0.1.2 | aarch64 builds; Ubuntu 22.04 and 24.04, Debian 12 and 13 |
| 0.1.3 | Ubuntu 26.04 |
| 0.1.4 | extra env variables per site; scheduled resets for demos |
| 0.1.5 | apps that follow their manifest URL; `setu upgrade` |

Some limits are honest gaps in 0.1.x: backups stay on the server and are not encrypted, disk use is reported but not enforced, sites cannot move between servers, there is no two-factor sign-in, and sites on one box are isolated as processes, not as VMs.

## 0.2: "runs anything, loses nothing"

0.2 is the next release, and its design is written and approved. Its goal is that a site is as safe on a box that may die as on one that will not.

- **Containers as a runtime.** Rootless Podman, one container per site running as the site's own user, under the same systemd unit name, the same limits drop-in and the same journal as binary sites. Images are pinned by digest; a tag is a validation error. The manifest already has `run.kind = "image"`, which validates today and becomes provisionable.
- **Off-box backups.** One S3-compatible target per panel (R2, S3, MinIO, Hetzner Object Storage and similar). Archives are encrypted with age before they leave the server. The control plane hands agents short-lived presigned URLs, so servers hold no S3 credentials. A weekly restore check restores one site's newest backup into a scratch database.
- **Site move and server drain.** A `move_site` job backs up, provisions on the target with the same env, restores, health-checks and flips Caddy routes. Drain moves every site off a server, one at a time.
- **Agent self-update** from the control plane, so other servers no longer need a manual `setu upgrade`.
- **Cloudflare tunnel ingress**, for servers without a public IP. Covered in more detail in [putting Cloudflare in front of Setu](post:cloudflare-in-front-of-setu).
- **Enforced disk quotas** on XFS with project quotas, report-only elsewhere, with the UI saying which.
- **Deletion grace**: a deleted site is kept for 24 hours with an undo.
- **Two-factor sign-in** (TOTP, with recovery codes), enforceable panel-wide, and **alerts** by email or signed webhook for failed sites, offline servers, failed backups and full disks.
- **Metrics history**: 90 days, with 24-hour sparklines on the site page.

A 0.1.x agent keeps working against a 0.2 control plane for everything that existed in 0.1. Migrations remain forward-only.

## 0.3: a hosted control plane

The order after 0.2 was decided on 2026-10-10: hosted control plane first, catalogue second, billing third. 0.3 is a Setu panel run for people who do not want to operate the panel itself; their own servers join it. In the roadmap's words, it is the cheapest way to learn whether anyone pays before building the provider product.

Its scope is small on purpose: two `setu serve` instances behind Caddy with leader election on the job runner (a Postgres advisory lock), teams with roles and scoped servers and sites, invitations, password reset and alert email, and a usage page per team.

## 0.4: the catalogue

Today an operator adds an app by pasting or linking a manifest. 0.4 aims for "publish once, install anywhere":

- a public registry of signed manifests (ed25519), with channels such as `stable` and `beta`, version pinning and update badges;
- a "Deploy to Setu" button that opens the panel's new-site dialog with a manifest prefilled;
- manifest v2: several processes per app (web and worker), cron entries, pre-start and post-provision hooks, sidecars such as Redis, and building from a Git tag for authors who do not publish binaries;
- author tooling: `setu manifest validate|sign|publish` and a GitHub Action that publishes on release.

Until then, [writing a Setu manifest](post:writing-a-setu-manifest) is the way in, and the community manifests live at github.com/setucp/manifests.

## 0.5: customers and billing

0.5 is for hosting providers: a customer signs up, picks a plan, pays and gets a site. It covers customers and a customer portal, plans with prices and quotas, Stripe-based billing with grace periods and suspension, placement policies across server groups, SMTP email and per-customer support scoping. Several design questions are still open, such as which payment providers to support for tax handling.

## 1.0: a bar, not a date

The roadmap does not give a date for 1.0. It gives a condition: 1.0 ships when a paying fleet has run on Setu for a quarter. Until then, expect rough edges and breaking changes, which is what the 0.x version number says.

### Later, and never

Some items are listed as later and unscheduled: Postgres as a managed service across servers, a Kubernetes runtime behind the same runtime interface, edge caching and WAF policies through Cloudflare's API, audit log export and SSO for operators. A Windows Server agent is listed as unlikely.

One thing is out of scope for good: managed interpreted runtimes. Setu will not manage PHP, Node or Python installs on the server. Apps that need an interpreter will ship as a container image instead. That keeps the promise from [why Setu exists](post:why-setu-exists): no runtime to maintain on the server.

## How to follow along and help

- The roadmap lives at [setucp.com/docs/roadmap](https://setucp.com/docs/roadmap) and in the repository, where each release's design spec appears before it ships.
- Release notes are in the changelog on [GitHub](https://github.com/setucp/setu).
- Bug reports, questions and app manifests are welcome as GitHub issues; for anything larger than a fix, open an issue to discuss it first.
- To try what exists today, start with the [install guide](https://setucp.com/install).
