---
title: Lessons from building Setu, a control panel for binaries
seo_title: Lessons from building Setu: what reviews caught | Setu
seo_description: Lessons from building Setu: what design reviews caught, why root work became typed verbs, why rollback restores the database, why tests use real systemd.
keyphrase: lessons from building Setu
excerpt: Setu's first design looked sound and was not. Here is what independent reviews caught before any code shipped, and the habits that came out of it: typed root, real-systemd tests, honest scope.
category: Engineering
tags: engineering, design review, security, testing, rust
cover_kicker: Engineering notes
cover_alt: A design review table with critical findings and their resolutions next to Setu's architecture diagram
---
Setu's design document went through three revisions and two independent reviews before the first release, and the first review's verdict was blunt: architecture sound, plan not executable without security-critical guessing. Most lessons from building Setu come from that gap between a design that reads well and one that survives contact with root, systemd and real apps. These are the parts worth passing on.

## Security lessons from building Setu

### 1. A "small" root helper is not small if it takes paths

The first design had the agent call a privileged helper with operations like "write this file at this path with this mode". The review called it root-equivalent: a prefix check on a path is defeated by symlinks, setuid bits or a well-placed systemd drop-in, and a bare `systemd-run` in sudoers was root by itself.

The fix shaped the whole system. The helper now takes **typed verbs** with JSON on stdin, and nothing path-like, no mode and no owner ever crosses sudo. Every path derives from a validated eight-character site id. Directories are opened step by step without following symlinks. Archives are checked entry by entry, and one bad entry refuses the whole install. The sudoers file shrank to two lines.

The lesson: when you design a privileged interface, list what the caller can choose. Every free-form field is a way out. [Inside the privileged helper](post:privileged-helper-design) has the verb table.

### 2. Check what is listening, not what you configured

Two of the first review's critical findings were about the network, not code. Caddy's admin API on TCP port 2019 would have been reachable by every hosted app on the box, so any site could rewrite every other site's routes. And Vyasa at the time bound `0.0.0.0`, so sites would have been reachable on their ports directly, past Caddy.

Neither was a bug in Setu's code. Both were defaults of the components around it. The answers were layered: Caddy's admin moved to a unix socket owned by group `caddy`; manifests gained a `bind_addr` source that hands apps `127.0.0.1:<port>`; and an nftables table drops outside traffic to the site port range in case an app binds wide anyway. `setu agent doctor` and the end-to-end test both check that port 2019 is closed. The same goes for the panel itself: in the shipped design it has no TCP listener on an installer box, only a unix socket behind Caddy, so a site on the same machine cannot forge client IPs at the panel.

## Reliability lessons

### 3. Rollback means the database too

The obvious rollback for a failed update is "put the old binary back". The review showed why that is not enough: if the new version ran migrations before failing health, the old binary meets a schema it does not know and refuses to start (with sqlx, the error is `VersionMissing`). The rollback "works" and the site stays down.

So Setu takes a backup before every update, and when the new version already ran, the rollback restores the database and directories too. The second review found one more gap: `pg_restore --clean` keeps objects that the failed version created. Restore now **replaces** the database: drop, recreate, restore.

The test app is built to make a bad rollback visible. Its version 0.1.2 adds a table and then fails health; 0.1.1 refuses to boot if that table exists. If the rollback ever forgets the database, the end-to-end test fails loudly. More in [safe updates, backup first](post:safe-updates-backup-first).

### 4. Assume every process restarts at the worst moment

The first plan did not say what happens when the control plane restarts mid-job. The answer was "the job stays `running` forever and the site is locked". Now jobs have leases and a stored step cursor; a restarted control plane reclaims expired leases and resumes from the step it was on. Every agent command is idempotent, results are written to disk before they are posted, and duplicates return the cached result.

This is tested directly. One end-to-end assertion makes the agent exit right after a step, before reporting it, then restarts it and checks the job finishes with that step run exactly once.

### 5. Keep secrets off argv, everywhere

Secrets have a habit of leaking through side doors: process lists, shell history, sudo logs, error messages. The review caught a Postgres password passed with `psql -v`. In the shipped design, role passwords travel as a `\set` line on stdin, `pg_dump` gets its password in its environment, join tokens come from an environment variable or stdin, and secrets in the command queue are blanked as soon as a command finishes.

## Process lessons

### 6. Test against the real thing

Unit tests with fakes are necessary, but they cannot tell you that a systemd unit actually starts or that a cgroup limit actually applies. Setu's end-to-end test runs the agent in a container with real systemd, Postgres, Caddy and nftables, and checks 14 named assertions: provisioning, TLS, ownership and modes, the firewall, the closed admin port, limits, backup and restore, update, rollback with database restore, an agent killed mid-command, delete, a real Vyasa site, a restart, and a lost Caddy config repaired by reconcile. The installer has its own 9-assertion test.

The debugging notes end with a rule worth stealing: **fix the code, never the assertion.**

Real components surface real surprises. sudo-rs's `visudo` rejected a `Defaults` line that classic sudo accepted, so the line was dropped and both now parse the two-line file. Deploying the panel into a container found that a pre-existing `/var/lib/caddy` left Caddy unable to write its internal CA, fixed before the release.

### 7. Cut scope out loud

Phase 1 shipped without containers, off-box backups, site moves, two-factor sign-in, enforced disk quotas and a CLI client. Each cut is written down in the spec, the README and the security docs, often in bold: backups are **not encrypted** and **not copied off the box**; disk is reported, not enforced. Saying what is missing turned out to be as useful to operators as describing what exists, and it keeps the [roadmap](post:setu-roadmap) honest.

### 8. Measure, then claim

The goal was a working Vyasa site in under 60 seconds. The end-to-end run on the development host measured about 8 seconds for the test app and about 9 for Vyasa 0.2.0. A measurement on real hosting hardware was still open. Numbers should come with where they were taken.

## Next steps

- Read the [trust model](https://setucp.com/docs/trust) that came out of these reviews.
- See the result on a server of your own with the [install guide](https://setucp.com/install).
