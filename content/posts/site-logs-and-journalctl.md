---
title: Reading site logs in Setu, from the panel and journalctl
seo_title: Site logs in Setu with the panel and journalctl | Setu
seo_description: Where Setu site logs live and how to read them, from the Logs tab and live job logs to journalctl for each site, the agent, Caddy and the control plane.
keyphrase: site logs
excerpt: Setu keeps no log files of its own. Every site, the agent and the panel log to journald. Here is how to read them in the panel and on the server.
category: Operations
tags: logs, journalctl, systemd, troubleshooting, jobs
cover_kicker: Operations guide
cover_alt: Cover card for the post Reading site logs in Setu, from the panel and journalctl
---
When a site misbehaves, the first question is what it printed. Setu does not invent a log format or a log directory: every site runs as a systemd unit, so its output goes to journald like any other service. This post shows where site logs live, how to read them from the panel, and the `journalctl` commands for when you are on the server.

## Every site is a systemd unit

Each site runs as `setu-site@<short>.service`, where `<short>` is its eight-character id. Whatever the app writes to stdout and stderr lands in the journal under that unit. There is no separate log file to rotate and no log agent to install; journald's own retention applies.

The same holds for Setu's own parts:

| Unit | What it logs |
|---|---|
| `setu.service` | the control plane: API, job runner, scheduler |
| `setu-agent.service` | the agent on each server |
| `caddy-api.service` | Caddy, with its config in `/etc/caddy/setu.json` |
| `setu-site@<short>.service` | one per site |

## Site logs in the panel

The site page has a **Logs** tab. Behind it, the control plane asks the server's agent for the journal of that unit, starting from a journal cursor, and streams the lines to your browser over server-sent events (`GET /api/v1/sites/{id}/logs`). One page from the agent can hold up to 5000 lines, and the cursor means each request continues where the last one stopped.

A few rules keep this safe to leave open:

- the stream ends when you close the tab;
- a stream lives at most 30 minutes;
- carriage returns and line feeds inside a line are escaped, so an app cannot fake extra log lines.

The agent reads the journal as the `setu` user, which is in the `systemd-journal` group. Reading logs does not go through the privileged helper or need root.

## Job logs: what Setu itself did

Site logs show what the app did. Job logs show what Setu did to the site. Provisioning, updates, backups, restores, env changes and deletes all run as jobs with named steps, and each step logs `step <name>: ok` or an error.

![The Jobs page in the Setu panel listing recent jobs with their status](images/panel-jobs.png "The Jobs page lists every job; opening one tails its log live until it finishes.")

The Jobs page lists them, and opening a job tails its log live until the job finishes. A failed provision shows exactly which step failed, which is usually the fastest way to tell a bad checksum from an app that never answered its health check. A deleted site's jobs keep their rows, so the delete job's log stays readable afterwards.

## Reading site logs with journalctl

On the server, the commands come straight from the operations guide:

```bash
journalctl -u 'setu-site@<short>'   # one site
journalctl -u setu-agent            # the agent
journalctl -u setu                  # the control plane
journalctl -u caddy-api             # Caddy
```

The usual `journalctl` flags work as with any unit. To follow a site while you reproduce a problem:

```bash
journalctl -u 'setu-site@<short>' -f
```

The short id is shown in the panel and appears in the site's paths, such as `/srv/setu/sites/<short>/`. The agent and control plane read the `RUST_LOG` environment variable as their log filter, defaulting to `info`.

## What is redacted, and what is not

Setu works hard to keep secrets out of logs it writes. Job log lines replace every registered secret with `***`: stored env secrets, the password inside a database URL, env changes and update prompt answers. The agent replaces every database password and env value a command carried with `***` before it stores a result. More on this in [Environment variables and secrets in Setu](post:env-variables-and-secrets).

Application logs are the exception. The Logs tab returns the app's journal **verbatim**. Setu cannot know what an app prints, so an app that logs its own database URL, generated key or one-time admin password exposes it to every operator who can read logs. If you write apps for Setu, do not log your own secrets.

## When the logs say nothing

Sometimes a site fails before the app writes anything. Two checks help:

- **The job log.** A provision or update that stops at `install` never started the app; one that stops at `health` started it, but it did not answer 2xx within `startup_grace_s`.
- **The server itself.** `setu agent doctor` checks the helper, the sudoers file, Caddy's admin socket, nftables, Postgres and the connection to the control plane, one row each, and exits 1 on any failure.

```bash
setu agent doctor
```

## Next steps

For keeping an eye on a server between incidents, read [Monitoring a small VPS without a monitoring stack](post:monitoring-a-small-vps). The [operations guide](https://setucp.com/docs/operations) lists every unit and log, and [Safe app updates](post:safe-updates-backup-first) explains the update steps you will see in job logs.
