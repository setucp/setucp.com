---
title: What a hosting control panel should do, and what it shouldn't
seo_title: What a hosting control panel should do | Setu
seo_description: A hosting control panel holds root on your servers. These are the rules Setu follows about what a panel should own, and what it must leave alone.
keyphrase: hosting control panel
excerpt: A control panel holds a lot of power over your servers. These are the lines Setu draws between what a panel should do for you and what it should leave alone.
category: Engineering
tags: control panel, design, systemd, security, operations
cover_kicker: Design principles
cover_alt: The Setu Jobs page showing provisioning and backup jobs with their named steps
---
A hosting control panel is, in effect, root on every server it manages. That makes the question of what it should and should not do more than a matter of taste: every feature is something a bug, or an attacker, can also do. This post sets out the rules Setu follows, with the parts of the code and docs where each one shows up.

## A hosting control panel should own the repetitive work

The reason to have a panel at all is that hosting a site involves the same dozen steps every time. Setu's provisioning job is exactly that list, in order:

```text
validate → create user and dirs → create database → install binary →
switch version → write unit → write env → start → health check →
add Caddy route → verify → finish
```

Each step is something you could do by hand. The panel's value is doing all of them, the same way, every time, and recording what happened. Backups, updates, restarts and env changes are jobs of the same kind.

## It should be the source of truth, and say so

A panel and a server can disagree. Setu settles that by design: the control plane is the source of truth. It queues typed, idempotent commands, and agents long-poll for them over HTTPS. Agents connect out; nothing connects in to an agent, and the control plane never SSHes.

Idempotence is what makes this safe. A job stores its current step before running it, and every step can run twice without harm. If the control plane restarts or an agent dies mid-command, the job resumes from its stored step. Setu's end-to-end test kills the agent after it writes a unit during provisioning, restarts it, and checks the job still finishes with exactly one `write_unit` step in its log.

![The Setu Jobs page with recent jobs and their status](images/panel-jobs.png "Every action is a job with named steps and a log you can read.")

## It should keep its root access small

A panel needs root for some things: creating a user, writing a unit, installing a binary. It does not need a root shell. Setu's agent runs as the unprivileged `setu` user and reaches root only through nine typed helper verbs: `site-create`, `write-unit`, `write-env`, `install`, `switch-version`, `unit`, `backup`, `restore` and `site-remove`.

Each verb takes a validated eight-character site id on the command line and typed JSON on stdin. It never accepts a path, a mode or an owner from its caller; every path is derived from the site id. The honest summary from Setu's trust model applies to every panel: whoever controls the control plane controls every joined server. What a panel can do is make that root surface small, typed and auditable. [The Setu trust model](post:setu-trust-model) goes through it in detail.

## It should not touch what it did not create

This is the rule most panels get wrong, and the one that matters most on a server you also use for other things.

- Setu's firewall rules live in their own nftables table, `inet setu`. It never flushes the ruleset and leaves other tables alone.
- Caddy routes Setu writes have ids `setu-site-<short>` and `setu-panel`. Routes it did not write are never touched.
- When the agent reconciles, site directories under `/srv/setu/sites` and `site_*` databases it does not know about are logged as warnings, never deleted.
- SSH, Postgres listeners and everything else on the host are yours to firewall.

A panel that "cleans up" things it does not recognise will one day delete something you needed.

## It should not hide the operating system

Setu sites are ordinary systemd units, `setu-site@<short>.service`, with logs in the journal. If the panel is down, you can still run:

```bash
systemctl status 'setu-site@<short>'
journalctl -u 'setu-site@<short>'
setu agent doctor
```

`setu agent doctor` prints one row per check (the helper's ownership and mode, the sudoers file, Caddy's admin socket, the firewall table, Postgres, the control plane's `/healthz`) and exits 1 on any failure. A panel that is the only way to see what is running makes outages worse, not better.

## It should not act on its own where judgment is needed

Since 0.1.5, an app published from a manifest URL follows that URL: Setu checks it every 6 hours and publishes any new version, which then appears in each site's Updates tab. It stops there. Sites are never updated on their own, and a check never replaces a version that is already published, because a manifest names binaries and their checksums and an unattended re-publish must not swap what a running version installs.

The same restraint shows in secrets. Values are sealed at rest and masked in the UI. Revealing one needs the operator's own password, and every attempt is written to the audit log, including denied ones.

### It should be honest about its limits

Setu's docs list what it does not do yet: no enforced disk quotas (disk is reported), no network isolation between sites on one box, no encryption of local backups, no off-box backups, no two-factor sign-in. Sites on one server share the kernel, the Postgres instance and loopback. Saying so plainly lets you decide where each site belongs.

## Next steps

To see these rules in practice, [install Setu](post:install-setu-in-five-minutes) on a spare VPS and watch a provisioning job run step by step. For how these choices compare with other tools, read [Setu vs cPanel, Coolify and Dokku](post:setu-vs-cpanel-coolify-dokku). The security model is documented at [setucp.com/docs/security](https://setucp.com/docs/security).
