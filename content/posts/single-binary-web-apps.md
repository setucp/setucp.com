---
title: Single-binary web apps are underrated, and easy to host
seo_title: Single-binary web apps are underrated | Setu
seo_description: Single-binary web apps need no runtime on the server and update by swapping one file. Here is why they suit a small VPS, and what they ask of you.
keyphrase: single-binary web apps
excerpt: A web app that ships as one executable needs no runtime, no build step and no image on the server. That makes it the easiest kind of app to host well.
category: Engineering
tags: rust, go, deployment, systemd, binaries
cover_kicker: Engineering notes
cover_alt: A terminal showing one release archive and its SHA256SUMS file next to a running systemd service
---
Single-binary web apps are a quiet advantage of Rust and Go: the release is one executable, and the server needs nothing else installed to run it. Yet most hosting tools are built around interpreters, build steps or container images, and treat a binary as a special case. This post argues the opposite: a single binary is the easiest kind of web app to host well.

## What "single binary" means here

A single-binary web app is a program that ships as one executable, usually in a tarball, sometimes as the bare file. It reads its configuration from the environment, binds an address it is given, talks to a database over a URL, and keeps its state in a database and a few directories.

Rust and Go make this the default. A statically linked build, for example a musl target in Rust, does not even depend on the server's C library. Setu itself is built that way: one static musl archive per release, for x86_64 and aarch64.

## Why single-binary web apps are easy to run

**Nothing to build on the server.** There is no compiler, package manager or dependency tree on the box. The server downloads a file, checks its checksum and runs it.

**Nothing to keep patched beneath the app.** An interpreted app needs a language runtime on the server, which has its own release and security cycle. A compiled app carries what it needs. You update the app, and that is the whole update.

**Updates are a file swap.** A new version is a new executable. Keep the old one next to it and rollback is a pointer change. Setu installs each version under `bin/<version>/` and switches a `bin/current` symlink atomically:

```text
/srv/setu/sites/<short>/bin/current -> bin/<version>/
/srv/setu/sites/<short>/data/      # the app's persistent directories
/srv/setu/sites/<short>/run/
/srv/setu/sites/<short>/env        # root:root 0600, read by systemd
```

**systemd is enough.** A binary is a process, and systemd already knows how to run processes: as a dedicated user, with memory and CPU limits from cgroups, with hardening such as `ProtectSystem=strict` and `NoNewPrivileges=yes`, and with logs in the journal. You do not need a container runtime to get isolation of the kind a small VPS needs.

**Small and predictable.** One process per site, a known memory ceiling, logs in one place. On a small server that predictability matters more than anything else. We look at the numbers side of this in [running many sites on one small VPS](post:many-sites-one-small-vps).

## What they ask of you

The ease is not free. A single-binary app has to follow a short contract so that something else can run it. Setu's version of that contract is:

1. Ship one binary in a tarball (or as the bare executable).
2. Read the address to bind, and everything else, from environment variables.
3. Answer `2xx` on a health path when ready, and only then.
4. Keep persistent state only in the declared directories and the database.

Rule 3 does real work. Setu polls the health path every 500 ms after a start, until it answers or the app's `startup_grace_s` runs out (90 seconds by default). A provision that never turns healthy fails; an update that never turns healthy rolls back. So the app should say it is ready only when it can actually serve: database migrated, first-boot work done.

Rule 4 is what makes backups honest. If all state lives in the database and the declared directories, a backup of those two things is a backup of the site.

## Describing one to Setu

The contract fits in a manifest. This is the core of the `hello` example from Setu's README:

```toml
schema = 1

[app]
id = "hello"
name = "Hello"
version = "0.1.0"
homepage = "https://example.com"
health = "/healthz"
admin_path = "/"

[run]
kind = "binary"
args = ["serve"]
[run.binary."x86_64-linux"]
url = "https://example.com/hello-0.1.0-x86_64-unknown-linux-musl.tar.gz"
sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
exec = "hello-0.1.0/hello"

[needs]
postgres = ">=16"
dirs = ["notes"]

[env]
HELLO_BIND = { from = "bind_addr" }
DATABASE_URL = { from = "postgres_url" }
HELLO_NOTES_DIR = { from = "dir", dir = "notes" }
HELLO_TOKEN = { generate = "hex32", secret = true }
```

It is shortened: a complete manifest also has `[limits.default]`, `[backup]` and `[update]` tables. Many Go projects publish a bare executable rather than an archive; `format = "binary"` on a target says the download is the executable itself. The Miniflux manifest in the [manifests repository](https://github.com/setucp/manifests) uses it.

## Where binaries are not the answer

Some apps need an interpreter, a headless browser or a sidecar process. A single binary does not fit them, and pretending otherwise helps nobody. Setu's answer is containers in phase 2, with rootless Podman under systemd, and it will never manage PHP, Node or Python runtimes directly. For everything that does compile to one file, the simpler path is worth taking.

## Next steps

If you maintain an app that already ships a release binary, [packaging it for Setu](post:package-your-app-for-setu) is mostly writing the manifest. The field reference is at [setucp.com/docs/manifest](https://setucp.com/docs/manifest), and the reasoning behind Setu as a whole is in [why Setu exists](post:why-setu-exists).
