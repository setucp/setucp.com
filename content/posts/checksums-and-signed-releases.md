---
title: Release checksums and signing, and what Setu verifies today
seo_title: Release checksums in Setu, and what is verified | Setu
seo_description: Every place Setu checks release checksums, from its installer and upgrades to app binaries and pinned keys, and where signed manifests fit on the roadmap.
keyphrase: release checksums
excerpt: Setu verifies every binary it installs against a SHA-256. Here is each check, what a checksum does and does not prove, and where signatures fit in.
category: Engineering
tags: security, sha256, releases, supply chain, manifests
cover_kicker: Supply chain
cover_alt: Cover card for the post Release checksums and signing, and what Setu verifies today
---
A control panel downloads a lot of software: its own binary, a database server, a web server, and every app it runs. Each download is a chance to install something other than what you meant. Setu's answer today is release checksums, checked at every step, and this post lists each one plainly, including what is not signed yet.

## Setu's own releases: SHA256SUMS

Each Setu release on GitHub has four files: an x86_64 archive, an aarch64 archive, `install.sh`, and `SHA256SUMS` listing exactly those archives and the installer. The archives are static musl builds, one per architecture, built natively by the release workflow.

The installer downloads the archive for your machine and the sums file, then refuses to continue unless the archive's line matches:

```bash
curl -fsSLO https://github.com/setucp/setu/releases/latest/download/install.sh
sudo bash install.sh --panel-host panel.example.com
```

The same check is available by hand, which is what the manual install in the docs uses:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

Upgrades follow the same rule. `setu upgrade`, added in 0.1.5, downloads the release archive and `SHA256SUMS`, refuses a checksum mismatch, and checks that the new binary reports the version you asked for before it installs anything. On the control-plane box it then backs up the panel database first. That command is covered in [Upgrading Setu itself](post:upgrading-setu-itself).

## App binaries: checked twice

Every app manifest pins its download per architecture with a sha256. From the Vyasa 0.3.3 manifest:

```toml
[run.binary."x86_64-linux"]
url = "https://github.com/vyasa-cms/vyasa/releases/download/v0.3.3/vyasa-0.3.3-x86_64-unknown-linux-gnu.tar.gz"
sha256 = "dd0de24ccd25aac0939fe96437157dcddeef8e2543b22edab30e1393aef6d658"
exec = "vyasa-0.3.3-x86_64-unknown-linux-gnu/vyasa"
```

The agent fetches the URL over HTTPS and verifies the hash. Then the root helper opens the downloaded file again and re-hashes it before extracting anything. Two processes, two checks: the root step never takes the unprivileged agent's word for what is in the file. A bad checksum during an update fails the `install` step, and at that point the running site has not been touched.

The checksum also anchors the version. A release URL is pinned per version, and a new upstream version is a new manifest version: you bump `app.version`, `url` and `sha256` together.

## Where an app checksum should come from

The manifests repository is specific about this: put the sha256 *you computed from the downloaded file* with `sha256sum`, not one copied from a web page. Its automated Vyasa workflow follows the same rule; `tools/bump-vyasa.py` downloads each archive and computes its hash itself before opening a pull request.

When Setu follows a manifest URL (0.1.5), it never replaces a version that is already published, even if the manifest at that URL changes. A manifest names binaries and their checksums, and an unattended re-publish must not swap what a running version installs. See [Followed manifests](post:followed-manifests-update-notices).

## Third-party packages: pinned keys

The installer also brings PostgreSQL and Caddy, and both paths are pinned:

- **PostgreSQL** comes from the PGDG apt repository on distributions without a suitable version (Ubuntu 22.04, Debian 12). The repository key is checked against a SHA-256 pinned in `install.sh` before apt ever sees it; on a mismatch the script stops and leaves apt unchanged.
- **Caddy** comes from Caddy's official apt repository. If that fails, the agent installs Caddy's own release package for the machine, checked against a pinned SHA-512 for that architecture.

## What release checksums prove, and what they do not

A checksum proves the bytes you got are the bytes the sums file describes. That catches corruption, a truncated download, and a tampered mirror or cache. It is only as strong as the place the sums file came from: here, the same GitHub release over HTTPS. Someone who could replace both the archive and `SHA256SUMS` on the release would not be stopped by the checksum alone.

That is the gap a signature closes. A signature made with a key held offline ties the release to its author, not just to the download location. Setu releases are **not signed** today, and we would rather say so than imply otherwise.

## Signed manifests on the roadmap

The roadmap's 0.4 "catalogue" phase plans a public registry of signed manifests, using ed25519 in the same model as the Vyasa marketplace: an index at a static URL, per-app channels, version pinning, and author tooling with `setu manifest validate|sign|publish`. Who runs the official registry and holds its signing key is listed as an open design question. Until then, the checks above are what stands between a download and your server.

## Next steps

Read the [install guide](https://setucp.com/docs/install) for the full installer sequence and the [roadmap](https://setucp.com/docs/roadmap) for the catalogue phase. To see how a manifest pins its binaries, read [App manifests explained](post:app-manifests-explained).
