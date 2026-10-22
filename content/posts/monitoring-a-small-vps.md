---
title: Monitoring a small VPS without a monitoring stack
seo_title: Monitoring a small VPS without extra tools | Setu
seo_description: Monitoring a small VPS with what Setu already collects, from heartbeats and per-site memory, CPU and disk to health endpoints and doctor checks.
keyphrase: monitoring a small VPS
excerpt: For one or two servers, a full metrics stack can cost more than the sites it watches. Here is what Setu already measures, where to see it, and what is missing.
category: Operations
tags: monitoring, metrics, vps, health, operations
cover_kicker: Operations guide
cover_alt: Cover card for the post Monitoring a small VPS without a monitoring stack
---
A metrics database, an exporter per service, a dashboard and an alert manager make sense for a fleet. On one small server they can use more memory than the sites they watch. Monitoring a small VPS can start with what the control panel already collects, and this post shows what Setu measures, where it shows it, and the gaps you should cover yourself.

## The heartbeat: what Setu measures

Each server's agent sends a heartbeat to the control plane every 15 seconds. It carries:

- the server's load average (`load1`), free memory and free disk;
- the state of each site's unit;
- each site's CPU and memory, read from systemd's own accounting (`MemoryCurrent`, `CPUUsageNSec`) every beat.

Each site's data size is measured with `du` on its data directory at most every ten minutes and reused in between, so a large media folder does not turn every heartbeat into a disk walk.

The control plane keeps site samples at one-minute resolution and prunes them after 30 days. A server's status is computed from the heartbeat: `online` when one arrived within the last 60 seconds, `offline` otherwise.

## Monitoring a small VPS from the panel

The Servers page lists each server with its latest load figures and status.

![The Servers page in the Setu panel with each server's status and load](images/panel-servers.png "The Servers page shows each server's status and its latest load, free memory and free disk.")

The Sites list shows each site's newest sample, with Memory and Disk as `used / limit`. The site page goes one level deeper: status, version, memory, disk and port on the overview, and bars against the plan's limits on the Limits tab.

![The overview of a site in the Setu panel showing status, version, memory, disk and port](images/panel-site.png "A site's overview: status, version, memory, disk and port at a glance.")

These are numbers, not charts. The design cut metric charts from the first release to ship sooner, so you see the latest sample rather than a history graph. For a handful of sites that is often enough to answer "which site is using the memory?"

## Health endpoints you can poll

Setu exposes plain HTTP health checks that any outside checker can use:

- the panel answers `/healthz` and `/readyz` without authentication;
- every site has a health path in its manifest, such as `/readyz` for Vyasa, which Setu itself polls during provisioning, updates and restores.

An external uptime check is still worth having, because a panel cannot report its own outage. The simplest version is a check from another machine, for example:

```bash
curl -fsS https://panel.example.com/healthz
```

Run it from a box that is not the one you are watching.

## setu agent doctor for the box itself

Load and memory say how busy a server is, not whether its plumbing is intact. For that, run the doctor on the server:

```bash
setu agent doctor
```

It prints one row per check and exits 1 on any failure:

| Row | Checks |
|---|---|
| `helper` | the binary's owner, mode and directory |
| `sudoers` | `visudo -cf /etc/sudoers.d/setu` |
| `caddy-api`, `caddy-socket` | Caddy is active and its admin socket answers |
| `caddy-tcp-2019` | nothing listens on `127.0.0.1:2019` |
| `nftables` | the `inet setu` table exists |
| `postgres` | `psql` as `postgres` answers |
| `control-plane` | the panel's `/healthz` answers 2xx |

Because it exits non-zero on failure, it fits a cron job that mails you its output.

## Backups are part of monitoring

A backup that silently stopped is as bad as a site that is down. Each site's Backups tab lists its backups and their status. For the control plane, **Settings → Panel** shows the last successful nightly dump of the panel database, and a failed attempt is shown there too and retried hourly.

![The Backups tab of a site in the Setu panel listing nightly and manual backups](images/panel-backups.png "A site's Backups tab lists each backup with its kind and status.")

Backups live on the same box in this release, so the check that matters most is whether your off-box copy of `/var/lib/setu/backups/` ran. See [How Setu backups work](post:how-setu-backups-work).

## What is missing today

Setu sends no alerts yet. The roadmap's 0.2 phase plans metrics kept 90 days at one-minute resolution, rolled up to hourly after 7 days, and email or webhook alerts when a site is `failed`, a server is `offline` for more than 5 minutes, a backup failed, or disk is above 90 %. Until then, the gaps are:

- **alerts**: cover them with an external uptime check and the doctor in cron;
- **disk limits**: `disk_mb` is reported, not enforced, so watch free disk on the Servers page;
- **history**: samples are kept for 30 days, but the panel shows the latest one.

## Next steps

When a number looks wrong, the next stop is the logs: [Reading site logs](post:site-logs-and-journalctl). To set sensible ceilings before anything goes wrong, read [Resource limits: memory and CPU per site](post:site-limits-memory-cpu). The [operations guide](https://setucp.com/docs/operations) has the full list of units and health checks.
