---
title: Writing a Setu manifest, step by step, with a real example
seo_title: Writing a Setu manifest, step by step | Setu
seo_description: Writing a Setu manifest table by table from the real Miniflux one: app, run, needs, env, limits, backup and update, then validating and publishing it.
keyphrase: Setu manifest
excerpt: A Setu manifest is one TOML file per app version, and it is all Setu knows about your app. We build one table at a time from the real Miniflux manifest, then validate and publish it.
category: Guides
tags: manifests, toml, app authors, miniflux
cover_kicker: Manifest guide
cover_alt: A TOML manifest for Miniflux open beside the Setu panel's Apps page
---
A Setu manifest is one TOML file per app version, and it is the only app-specific knowledge Setu has. Where to download the binary, how to build its environment, how to tell it is healthy, what to back up: all of it lives in this one file. This post writes one table at a time, using the real Miniflux manifest from the `setucp/manifests` repository, so every line below is one that has been provisioned and checked.

If you have not packaged your binary yet, start with [packaging apps for Setu](post:package-your-app-for-setu). For the concepts behind manifests, see app manifests explained, an earlier post in this series.

## The app and its binary

### Step 1: the schema and `[app]`

```toml
schema = 1

[app]
id = "miniflux"
name = "Miniflux"
version = "2.3.3"
homepage = "https://miniflux.app"
health = "/healthcheck"
admin_path = "/"
startup_grace_s = 60
```

- `id` must match `^[a-z][a-z0-9-]{1,31}$`. It ties every version of the app together.
- `version` must be valid semver. It also names the install directory, `bin/<version>/`.
- `health` is a path starting with `/`. Setu polls `127.0.0.1:<port><health>` and needs a `2xx` when the app is ready.
- `admin_path` is what the site page links to, `https://<domain><admin_path>`. Use `"/"` if the app has no separate admin.
- `startup_grace_s` (1–3600, default 90) is how long health may fail after a start.

### Step 2: `[run]` and the binary

```toml
[run]
kind = "binary"
args = []

[run.binary."x86_64-linux"]
url = "https://github.com/miniflux/v2/releases/download/2.3.3/miniflux-linux-amd64"
sha256 = "237bf0aed05e86c235b6bcfbad843bfc7bcdd6a628ece672eae3d1e013ddd244"
format = "binary"
exec = "miniflux"
```

`kind = "binary"` is the only runtime that provisions today; `"image"` validates but is refused until 0.2. Miniflux publishes a bare executable, so `format = "binary"` and `exec` is the single file name to install it under. For a `tar.gz` archive, leave `format` out and make `exec` the path inside the archive, as the Vyasa manifest does with `vyasa-0.3.3-x86_64-unknown-linux-gnu/vyasa`.

Declare at least one target, `x86_64-linux` or `aarch64-linux`. The Vyasa manifest declares both. `workdir` is optional: the default, `exec_dir`, runs the app from the folder that holds the executable.

## What the site needs

### Step 3: `[needs]`

```toml
[needs]
postgres = ">=13"
```

`[needs]` is required but may be empty. `postgres` gives the site its own database and role. `dirs` lists persistent directories under `data/`; Miniflux keeps everything in PostgreSQL, so it has none. Vyasa, by comparison, asks for three:

```toml
dirs = ["media", "index", "registry"]
```

### Step 4: `[env]`, where most of the work is

```toml
[env]
LISTEN_ADDR    = { from = "bind_addr" }
DATABASE_URL   = { from = "postgres_url" }
BASE_URL       = { from = "site_url" }
RUN_MIGRATIONS = { value = "1" }
CREATE_ADMIN   = { value = "1" }
ADMIN_USERNAME = { value = "admin" }
ADMIN_PASSWORD = { generate = "password20", secret = true, once = true }
```

Each variable has exactly one source:

| Source | Example | Gives |
|---|---|---|
| `from` | `bind_addr`, `port`, `postgres_url`, `dir`, `run_dir`, `owner_email`, `site_url` | a value Setu knows about the site |
| `generate` | `hex32`, `password20` | a random value, made once |
| `value` | `{ value = "1" }` | a constant |
| `prompt` | `{ prompt = "Label" }` | asked in the New-site dialog |

`secret = true` masks the value in the panel and seals it at rest; revealing it needs the operator's password and is audited. `postgres_url` is always treated as secret. `once = true` (which requires `secret`) writes the value for the first boot only, which is why Miniflux creates its admin at startup and only then passes health.

Every rule is resolved once, when the site is created, and stored sealed. On an update, generated and prompted values are kept by name, `from` and `value` are resolved again, and new rules are resolved fresh.

## Step 5: `[limits.default]`, `[backup]`, `[update]`

```toml
[limits.default]
memory_mb = 256
cpu_percent = 100
disk_mb = 1024

[backup]
postgres = true

[update]
strategy = "replace"
```

`[limits.default]` is the author's suggestion; the operator's plan overrides it. `cpu_percent = 100` is one core, and `disk_mb` is reported, not enforced, in 0.1.x. More in [memory and CPU limits per site](post:site-limits-memory-cpu).

`[backup] postgres = true` dumps the database in every backup. If the app has directories, `[backup] dirs` picks which ones to archive; Vyasa backs up `media` and `registry` but leaves out `index`, which it can rebuild. `[update] strategy = "replace"` is the only strategy in this version.

Unknown keys are an error. Every table except `[env]` is required.

## Validate and publish the Setu manifest

### Step 6: validate before you publish

The panel validates on **Apps → Add**, with line numbers. You can also check a file without storing anything, via `POST /api/v1/apps/validate`:

```bash
jq -Rs '{toml: .}' manifest.toml | curl -s -X POST https://panel.example.com/api/v1/apps/validate \
  -H 'Content-Type: application/json' -H 'Origin: https://panel.example.com' \
  --cookie 'setu_session=…' -d @-
```

The answer is `{"ok": …, "errors": […]}`. Errors name the field and line, for example:

```text
error: app.health must start with / line 8
error: env.HELLO_NOTES_DIR references dir "media" not in needs.dirs line 29
error: env.HELLO_TOKEN once requires secret = true line 31
```

These come from the validator's own test corpus, which is a good place to look when an error is unclear.

### Step 7: publish, preferably from a URL

You can paste the TOML, but publishing from a URL is better since 0.1.5:

```bash
curl -X POST https://panel.example.com/api/v1/apps \
  -H 'Content-Type: application/json' -H 'Origin: https://panel.example.com' \
  --cookie 'setu_session=…' \
  -d '{"url": "https://raw.githubusercontent.com/setucp/manifests/main/miniflux/manifest.toml"}'
```

An app published from a URL **follows** it: Setu fetches the URL every 6 hours and publishes any new version it finds, so it appears in each site's Updates tab. Sites are never updated on their own, and a check never replaces a version already published. Details in [followed manifests](post:followed-manifests-update-notices).

![The Apps page in the Setu panel, with an app card showing the manifest URL it follows](images/panel-apps.png "An app published from a URL shows what it follows, with Check now and Stop following.")

### When the app releases a new version

Bump `app.version`, `url` and `sha256` together, computing the checksum from the downloaded file. Each version is its own manifest; the URL of a published version should never start pointing at different bytes.

## Next steps

- The full field table is in the [manifest reference](https://setucp.com/docs/manifest).
- Contribute yours to [github.com/setucp/manifests](https://github.com/setucp/manifests): validate it, provision a site from it, then open a pull request.
- Try it on your own server via the [install guide](https://setucp.com/install).
