---
title: A Postgres database per site, and why Setu does it that way
seo_title: A Postgres database per site with Setu | Setu
seo_description: How Setu creates a Postgres database per site with its own role, keeps passwords off the command line, and backs up and restores each one alone.
keyphrase: Postgres database per site
excerpt: Every Setu site that needs PostgreSQL gets its own database and role on the server's local instance. Here is how they are created, isolated, backed up and restored.
category: Engineering
tags: postgres, database, backups, isolation, security
cover_kicker: Engineering notes
cover_alt: Cover card for the post A Postgres database per site, and why Setu does it that way
---
Sharing one database and one superuser across every app on a server is quick to set up and painful to live with. One leaked password exposes everything, and restoring one app means restoring all of them. Setu gives each site a Postgres database per site, with its own role, and this post walks through how that database is created, isolated, backed up and restored.

## A Postgres database per site, with its own role

A manifest asks for PostgreSQL in `[needs]`:

```toml
[needs]
postgres = ">=16"
```

Vyasa's manifest asks for `>=16`; Miniflux's asks for `>=13`. When a site is created, Setu allocates a database and a role, both named `site_<short>`, where `<short>` is the site's eight-character id. They live on the PostgreSQL instance of the server the site runs on. The installer brings that instance: PostgreSQL 16 on Ubuntu 22.04 and 24.04 and Debian 12, 17 on Debian 13, 18 on Ubuntu 26.04.

The app receives its connection string through the manifest's env rules:

```toml
[env]
VYASA_DATABASE_URL = { from = "postgres_url" }
```

That resolves to `postgres://site_<short>:<password>@127.0.0.1:5432/site_<short>`. A `postgres_url` value is always treated as secret: it is sealed at rest and masked in the panel for every role, whatever the manifest says.

## Creating it without leaking the password

The agent talks to Postgres as the `postgres` user through peer authentication, using the one sudo rule that allows `psql`, `pg_dump` and `pg_restore`. Creating the database is create-or-alter, run as a script on standard input:

- `\set pw '<value>'` puts the password in a psql variable;
- `CREATE ROLE … LOGIN` if the role is absent, then `ALTER ROLE … PASSWORD :'pw'`;
- `CREATE DATABASE … OWNER …` if it is absent;
- `REVOKE CONNECT ON DATABASE … FROM PUBLIC`.

The password never appears on a command line, so it does not show up in `ps` or the sudo log. Because the step is create-or-alter, a provisioning retry with the same sealed password converges on the same state instead of failing. The role password is minted once, at site creation, and kept inside the sealed `postgres_url`; there is no separate password column.

## Isolation between sites on one instance

The `REVOKE CONNECT … FROM PUBLIC` is what keeps one site's role out of another site's database, and a test asserts that another site's role cannot connect. `setu agent install` also revokes `CONNECT` on the `postgres` database and, on the panel box, on the control plane's own `setu` database.

What the sites do share is the instance itself. One site running heavy queries can slow its neighbours. Ubuntu's default PostgreSQL listens on localhost only, and Setu leaves the rest of Postgres's network exposure to you. The wider picture of what sites share is in [Running many sites on one small VPS](post:many-sites-one-small-vps).

## Backups with pg_dump

When a manifest says `[backup] postgres = true`, every backup of the site includes a custom-format dump:

```bash
sudo -n -u postgres pg_dump -Fc site_<short>
```

The agent writes it atomically to `/var/lib/setu/backups/<short>/<backup_id>/db.dump`, next to `dirs.tar.zst` for the site's directories. Nightly backups run at 03:00 with per-site jitter, and every update and restore takes its own safety backup first. These files are not encrypted and not copied off the box in this release, so copy `/var/lib/setu/backups/` elsewhere yourself. [How Setu backups work](post:how-setu-backups-work) covers retention.

## Restore replaces the database

A restore does not merge a dump into the existing database. It replaces it:

1. `DROP DATABASE … WITH (FORCE)`;
2. create the role if it is absent, create the database if it is absent, revoke `CONNECT` again;
3. `pg_restore --no-owner --role=<site role> -d <db>` from standard input.

The role and its password survive the drop, so the app reconnects with the same URL. Replacing matters most during a failed update. If a new version migrated the schema and then failed its health check, Setu restores the `pre_update` backup, and objects the failed version created do not survive. The site ends up on the old version with the old schema.

## Restoring into a new site by hand

The panel restores a backup only into the same, still existing site. If the site was deleted, its backups stay listed under **Backups**, and the operations guide shows a manual restore into a new site of the same app (short id `NEW`):

```bash
systemctl stop setu-site@NEW
sudo -u postgres pg_restore --clean --if-exists --no-owner --role=site_NEW -d site_NEW \
  < /var/lib/setu/backups/OLD/<backup_id>/db.dump
zstd -dc /var/lib/setu/backups/OLD/<backup_id>/dirs.tar.zst | tar -x -C /srv/setu/sites/NEW/data
chown -R setu-site-NEW:setu-site-NEW /srv/setu/sites/NEW/data
systemctl start setu-site@NEW
```

One caveat: the new site has its own generated secrets. For Vyasa that includes `VYASA_SECRET_KEY`, so data the app encrypted under the old site's key will not open with the new one.

## Next steps

A Postgres database per site on the local instance is the whole model in this release. Managed Postgres across servers, with a primary cluster and replicas, is listed on the [roadmap](https://setucp.com/docs/roadmap) under "later, unscheduled".

The agent's database commands are documented in the [agent docs](https://setucp.com/docs/agent), and backups and restores in the [operations guide](https://setucp.com/docs/operations). For the full restore flow from the panel, read [Restoring a site from a backup](post:restoring-a-backup).
