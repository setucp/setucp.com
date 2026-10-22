---
title: Packaging apps for Setu: the binary, the archive, the contract
seo_title: Packaging apps for Setu: a guide for app authors | Setu
seo_description: Packaging apps for Setu takes one binary and a few rules: read config from env, bind where told, answer health when ready. Archive rules and checksums inside.
keyphrase: packaging apps for Setu
excerpt: Setu runs any compiled web app that follows a short contract. This guide covers the binary, the archive layout, the rules the installer enforces, and app behaviour that keeps updates safe.
category: Guides
tags: packaging, rust, go, releases, app authors
cover_kicker: App author guide
cover_alt: A release archive with one top-level folder holding a single executable, next to its sha256 checksum
---
Setu does not build anything on the server and has no runtime to manage. It downloads a published binary, checks it, and runs it as a systemd service. That makes packaging apps for Setu mostly a question of what you publish and how your app behaves when it starts. This guide covers both halves; the manifest that describes the result has its own walkthrough.

## What packaging apps for Setu requires

The Setu README states the whole deal for app authors:

1. Ship one static binary in a tarball (or as a bare executable).
2. Read the address to bind, and everything else, from environment variables the manifest declares.
3. Answer `2xx` on the health path when ready.
4. Keep persistent state only in the declared directories and the database.

If your app already does this, you are nearly done. Rust, Go, Zig and other compiled languages fit naturally; apps that need an interpreter are expected to ship as a container image once 0.2 adds that runtime.

## Build the binary

A static binary removes any dependency on the server's system libraries. For Rust, the musl target does that. Setu's own sample app, `hello-axum`, is built like this:

```bash
CC_x86_64_unknown_linux_musl=clang \
  cargo build --release --target x86_64-unknown-linux-musl -p hello
```

The `CC_…=clang` part is only needed when `musl-gcc` is not installed; crates with C code (such as `ring`) need some C compiler for the target. Go projects often publish a ready-made executable per platform already; Miniflux, a Go feed reader, does, and Setu's sample manifest uses it as is.

Setu supports two targets in manifests, `x86_64-linux` and `aarch64-linux`. A site is only placed on a server whose architecture the manifest covers, so publish both if you can.

## Choose a release format

There are two, and the manifest says which one you use. Setu never guesses from the bytes.

**A `tar.gz` archive** (the default). Put one top-level folder in it, named after the release, holding the executable and anything it needs next to it:

```text
hello-axum-0.1.0-x86_64-unknown-linux-musl/
  hello      static musl executable
  VERSION
```

```bash
tar -czf hello-axum-0.1.0-x86_64-unknown-linux-musl.tar.gz \
  hello-axum-0.1.0-x86_64-unknown-linux-musl/
```

The manifest's `exec` is then the path inside the archive, `hello-axum-0.1.0-x86_64-unknown-linux-musl/hello`. By default Setu runs the app with its working directory set to the folder that holds `exec`, which is how Vyasa finds its admin assets next to the binary.

**A bare executable** with `format = "binary"`. The download is the program itself, like Miniflux's `miniflux-linux-amd64`. Setu verifies it and installs it under the file name you give in `exec` (one name, no `/`), mode 0755.

## What the installer refuses

The archive is extracted by Setu's privileged helper, which runs as root, so it is strict. The whole install fails, with nothing left behind, if any entry is:

- a symlink, a hard link or a device file;
- an absolute path, or a path containing `..`;
- marked setuid, setgid or sticky.

Build archives from a plain directory of regular files and you will not hit any of these. Installed binaries are owned by root and the `bin/` tree is not writable by the app, so do not plan on writing next to your executable at runtime.

## Publish a checksum computed from the file

Every manifest target carries a `sha256` of the download. The agent checks it after downloading and the root helper checks it again before installing. Compute it from the exact file you uploaded:

```bash
sha256sum hello-axum-0.1.0-x86_64-unknown-linux-musl.tar.gz
```

The manifests repository asks for the same discipline from contributors: put the sha256 you computed from the downloaded file, not one copied from a web page. Its Vyasa bump script downloads each archive and hashes the bytes itself. Release URLs are pinned per version, so never replace an asset in place: a new build is a new version. [Checksums and signed releases](post:checksums-and-signed-releases) explains why this matters.

## Make the app behave

The binary is half of the package. The other half is behaviour Setu relies on.

**Bind where you are told.** Setu gives each site a port from 20000–29999 and can hand your app `127.0.0.1:<port>` (`from = "bind_addr"`) or just the port. Bind the loopback address when you can. The firewall drops outside traffic to that range anyway, but binding loopback means Caddy is the only client by construction.

**Take all configuration from the environment.** Database URL, directories, secrets and the public URL can all come from the manifest's `[env]` table. Values never contain control characters, so you do not need to handle quoting.

**Write only where you may.** Units run with `ProtectSystem=strict`. Your app can write its declared directories under `data/` and its `run/` directory, and nothing else.

**Report healthy only when you can serve.** Setu polls the health path every 500 ms until it answers `2xx` or the startup grace (90 seconds by default) runs out. Run your migrations first, then pass health. A failed health check fails provisioning, or rolls an update back.

**Migrate on boot, and expect rollbacks.** When an update fails health after the new version started, Setu restores the database and directories from the backup it took before the update, then starts the old binary. Your old version will therefore see the old schema, not the new one. The `hello` test app proves this on every release: its 0.1.2 migrates and then fails health, and the rollback must leave 0.1.1 running on its old tables.

**Consume one-time values before reporting healthy.** A manifest can mark a generated admin password `once = true`. It is written to the env file for the first boot only and removed after the first successful health check. Create the admin account at boot, then let health pass.

**Do not log secrets.** The site's Logs tab returns your app's journal verbatim. Setu redacts what it handles, but it cannot know what your app prints.

## Next steps

- Describe the package in a manifest: [writing a Setu manifest, step by step](post:writing-a-setu-manifest).
- See why one file is a good unit of deployment in [single-binary web apps are underrated](post:single-binary-web-apps).
- Field-by-field rules are in the [manifest reference](https://setucp.com/docs/manifest).
