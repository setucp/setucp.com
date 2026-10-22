---
title: App manifests explained, the one file Setu needs per app
seo_title: App manifest explained, how Setu runs an app | Setu
seo_description: A Setu app manifest is one TOML file per version. Learn each table, from binaries and checksums to env rules, limits and backups, with the real Vyasa example.
keyphrase: app manifest
excerpt: Setu knows nothing about your app except one TOML file per version. Here is what each table in that app manifest does, using the real Vyasa manifest.
category: Guides
tags: manifest, toml, apps, vyasa, packaging
cover_kicker: Manifest guide
cover_alt: Cover card for the post App manifests explained, the one file Setu needs per app
---
Setu has no built-in knowledge of Vyasa, Miniflux or any other app it runs. Everything it needs comes from an app manifest: one TOML file per app version, pasted into the panel or published at a URL. If you understand that file, you understand what Setu will do with your app. This post reads one real manifest table by table.

## What an app manifest is for

A manifest answers a fixed set of questions: where to download the release and its sha256, which executable to run, whether the app needs a PostgreSQL database or persistent directories, how its environment is built, which health endpoint says it is ready, its default resource limits, and what a backup holds.

That is the whole contract for app authors: ship a static binary, read the bind address and everything else from environment variables the manifest declares, answer 2xx on the health path when ready, and keep persistent state only in the declared directories and the database.

## The `[app]` table: identity and health

Here is the top of the Vyasa 0.3.3 manifest from the setucp manifests repository:

```toml
schema = 1

[app]
id = "vyasa"
name = "Vyasa"
version = "0.3.3"
homepage = "https://github.com/vyasa-cms/vyasa"
health = "/readyz"
admin_path = "/admin"
startup_grace_s = 90
```

- `id` matches `^[a-z][a-z0-9-]{1,31}$`; `version` must be semver, because it names the `bin/<version>/` directory.
- `health` is polled on `127.0.0.1:<port>` every 500 ms until it answers 2xx or `startup_grace_s` runs out (default 90, range 1–3600). A failure fails provisioning, or rolls back an update.
- `admin_path` is what the site page links to, here `https://<domain>/admin`.

The app should only return 2xx once it can actually serve: database migrated, first admin created.

## The `[run]` table: what to download and execute

```toml
[run]
kind = "binary"
workdir = "exec_dir"
args = ["serve"]
[run.binary."x86_64-linux"]
url = "https://github.com/vyasa-cms/vyasa/releases/download/v0.3.3/vyasa-0.3.3-x86_64-unknown-linux-gnu.tar.gz"
sha256 = "dd0de24ccd25aac0939fe96437157dcddeef8e2543b22edab30e1393aef6d658"
exec = "vyasa-0.3.3-x86_64-unknown-linux-gnu/vyasa"
```

The Vyasa manifest also declares an `aarch64-linux` target. A manifest needs at least one of the two, and a site is only placed on a server whose architecture it covers.

`kind = "binary"` is the only kind that provisions today; `"image"` validates but is refused until containers land. The default download is a `.tar.gz`, and `exec` is the path inside it. Many Go projects publish a bare executable instead, which is what `format = "binary"` is for; the Miniflux manifest uses it with `exec = "miniflux"`.

`workdir` picks the working directory: `exec_dir` (the folder holding `exec`), `bin` (the archive root) or `data`. Vyasa uses `exec_dir` because its admin assets sit next to the binary.

## `[needs]` and `[env]`: database, dirs and configuration

```toml
[needs]
postgres = ">=16"
dirs = ["media", "index", "registry"]
```

`postgres` gives the site its own database and role, covered in [A Postgres database per site](post:postgres-database-per-site). Each entry in `dirs` becomes `/srv/setu/sites/<short>/data/<name>`, owned by the site user.

The `[env]` table then wires all of it into the app. Each entry is `generate`, `from`, `value` or `prompt`, optionally `secret` and `once`. In Vyasa's case, `VYASA_BIND_ADDR = { from = "bind_addr" }` becomes `127.0.0.1:<port>`, `VYASA_DATABASE_URL = { from = "postgres_url" }` becomes the site's database URL, and `VYASA_ADMIN_PASSWORD` is a one-time generated password. The full rules are in [Environment variables and secrets in Setu](post:env-variables-and-secrets).

## Limits, backup and update

```toml
[limits.default]
memory_mb = 512
cpu_percent = 100
disk_mb = 5120

[backup]
postgres = true
dirs = ["media", "registry"]

[update]
strategy = "replace"
```

`[limits.default]` sets memory and CPU (100 is one core); the plan's limits override them, and `disk_mb` is reported, not enforced. `[backup]` says to dump the database and archive `media` and `registry`, leaving out `index`, which Vyasa can rebuild. `"replace"` is the only update strategy in this version.

Every table except `[env]` is required, and unknown keys are an error.

## Validating before you publish

The validator is strict and specific. It names the key and line:

```text
error: app.health must start with / line 8
error: env.HELLO_TOKEN once requires secret = true line 31
error: unknown field 'colour' at [app] line 11
```

You can run it without storing anything: `POST /api/v1/apps/validate` with the raw TOML. To add an app, use **Apps → Add** in the panel and paste the file or its raw URL, or call the API:

```bash
curl -X POST https://<panel>/api/v1/apps \
  -H 'Content-Type: application/json' -H 'Origin: https://<panel>' \
  --cookie '<session>' \
  -d '{"url": "https://raw.githubusercontent.com/setucp/manifests/main/miniflux/manifest.toml"}'
```

Then create a site from it with **Sites → New**.

## Next steps

The field reference is in the [manifest docs](https://setucp.com/docs/manifest), and ready-made manifests for Vyasa, Miniflux and a Rust sample live in the manifests repository. To write one for your own app, follow [Writing a Setu manifest, step by step](post:writing-a-setu-manifest).
