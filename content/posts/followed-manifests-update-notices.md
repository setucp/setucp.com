---
title: Followed manifests in Setu, app updates that find you
seo_title: Followed manifests and app update notices in Setu | Setu
seo_description: With followed manifests, Setu 0.1.5 re-checks an app's manifest URL every 6 hours and offers new versions in each site's Updates tab, never updating on its own.
keyphrase: followed manifests
excerpt: Setu 0.1.5 re-checks the URL an app was published from and offers new versions in the Updates tab. Nothing updates on its own, and nothing published gets replaced.
category: News
tags: updates, manifests, release, apps, vyasa
cover_kicker: New in 0.1.5
cover_alt: Cover card for the post Followed manifests in Setu, app updates that find you
---
Before Setu 0.1.5, a new app version reached your sites only after someone noticed the release and published its manifest again by hand. That is easy to forget, and a forgotten update is usually a security fix you did not apply. Followed manifests remove that step: an app published from a URL keeps watching it, and new versions show up where you will see them.

## What following a manifest URL means

When you add an app from a URL (**Apps → Add** with a link, or `POST /api/v1/apps` with `{"url": …}`), Setu stores that URL as the app's source. From then on the app **follows** it.

Every 6 hours, on the scheduler tick, the control plane checks every followed app. A check:

1. fetches the URL with the same guards as publishing: public addresses only, no redirects, 10 seconds, 1 MiB;
2. parses and validates the manifest;
3. refuses a manifest whose `app.id` is not the followed app's;
4. publishes the version if it is not published yet, audited as `app.publish` with the detail `<app>/<version> (followed)`;
5. records when the check finished and its error, if any.

A failed check is recorded and retried at the next round. It is not treated as an error of the panel.

## Notices, not automatic updates

Publishing a version does not change any site. The new version appears in each site's **Updates** tab, and an operator decides when to move to it.

![The Updates tab of a site in the Setu panel, offering a newer app version](images/panel-updates.png "A site's Updates tab: a newly published version waits for an operator to apply it.")

When you do apply it, the usual update job runs: a `pre_update` backup, install, switch, start, health check, and an automatic rollback (database included, when the new version already ran) if health fails. That flow is described in [Safe app updates: backup first, every time](post:safe-updates-backup-first).

Keeping the choice with a person is deliberate. A small operator may want to read release notes first, or update a staging site before the real one.

## Why a check never replaces a published version

There is one rule in followed manifests that surprises people: a check **never replaces a version that is already published**, even when the manifest at the URL changed.

The reason is that a manifest names binaries and their checksums. If version 0.3.3 is published and running on your sites, and the file at the URL later says 0.3.3 points at different bytes, an unattended re-publish would silently change what that running version installs. Setu refuses to do that on its own. If you really mean to replace a published version, publish it again by hand; that still works as before.

## Managing followed manifests in the panel

![The Apps page in Setu with an app card that follows a manifest URL](images/panel-apps.png "An app card shows the URL it follows, with Check now and Stop following.")

On the Apps page, each followed app shows "Follows <url>" with the time of the last check, or the last error. Two actions sit next to it:

- **Check now** runs a check immediately, useful right after an upstream release.
- **Stop following** clears the source. The app and its published versions stay.

The same actions are in the API, for operators and owners:

```text
POST   /api/v1/apps/{id}/check    -> {"published": "<version>" | null, "source": {...}}
DELETE /api/v1/apps/{id}/source   -> stop following, audited as app.source_clear
```

Both return 404 when the app follows no URL. `AppOut` gains a `source` field: `{ url, checked_at, last_error }`, or `null`. Publishing pasted TOML leaves an existing source as it is; publishing from a new URL replaces it.

## How Vyasa updates reach the manifest

Following a URL only helps if someone updates the file at that URL. For Vyasa, the setucp manifests repository does it automatically. Its workflow `.github/workflows/vyasa-release.yml` checks for a new Vyasa release every six hours and opens a pull request moving `vyasa/manifest.toml` to it. The script behind it, `tools/bump-vyasa.py`, downloads each archive and computes its sha256 itself.

Once that pull request is merged, panels that follow the raw URL pick the new version up on their next check:

```text
https://raw.githubusercontent.com/setucp/manifests/main/vyasa/manifest.toml
```

The same pattern works for your own app: keep its manifest at a stable raw URL, bump `app.version`, `url` and `sha256` together on each release, and every panel following it sees the update.

## What is not covered

Following works with public URLs only. Private repositories that need authentication headers are out of scope for 0.1.5. Setu itself is not upgraded by this feature; that is the separate `setu upgrade` command from the same release.

## Next steps

Upgrade to 0.1.5 with `setu upgrade`. An app added from pasted TOML has no URL to follow, so add it from its raw manifest URL instead. The [operations guide](https://setucp.com/docs/operations) covers updates in full, and [App manifests explained](post:app-manifests-explained) shows what a manifest contains.
