---
title: Custom domains and automatic HTTPS with Caddy in Setu
seo_title: Automatic HTTPS with Caddy for every site | Setu
seo_description: How Setu gives every site a custom domain and automatic HTTPS with Caddy, from the DNS record to the route, the certificate and the internal CA option.
keyphrase: automatic HTTPS with Caddy
excerpt: Every Setu site gets its own domain and a certificate without you editing a Caddyfile. Here is how the route is built, and what to check when HTTPS does not come up.
category: Guides
tags: caddy, https, tls, domains, dns
cover_kicker: Domains and TLS
cover_alt: The Setu site overview showing the site's domain and a link to its admin page
---
Every site in Setu has a domain, and every domain gets automatic HTTPS with Caddy. You never write a Caddyfile: the agent programs Caddy directly, one route per domain, and Caddy fetches the certificates. This post explains how that works, what you need to provide, and how to check it when a certificate does not appear.

## What you provide: a DNS record

The one thing Setu cannot do for you is DNS. For each site, create a record pointing the site's domain at the public IP of the server that runs it. With ACME, the certificate authority has to reach your server under that name, so the record must exist and resolve before the certificate can be issued. Ports 80 and 443 must be open on the server.

You choose the domain when you create the site, in the New-site dialog. A few names are refused: the panel's own host, `localhost`, and a server's hostname. Domains are unique across the panel.

![The Setu site overview with domain, status and admin link](images/panel-site.png "The site overview shows the domain and links straight to the app's admin page.")

The domain also reaches the app if it asks for it. A manifest can declare `{ from = "site_url" }`, which resolves to `https://<domain>`, so the app knows its public URL without you typing it twice.

## How a domain gets automatic HTTPS with Caddy

Caddy on a Setu server runs as `caddy-api.service` with the config `/etc/caddy/setu.json`. It has one server, named `setu`, listening on `:443` with automatic HTTPS, and Caddy's automatic redirect from HTTP on `:80` to HTTPS.

When a site is provisioned, the agent adds a route with the id `setu-site-<short>`, where `<short>` is the site's eight-character id. The route sends the domain to `127.0.0.1:<port>`, the loopback port the site was given. It is added near the end of provisioning, after the app has passed its health check, so visitors never reach a site that is not ready. Provisioning then checks once more that the unit is still active, and removes the route if it is not.

Site ports come from the range 20000 to 29999. An nftables rule in Setu's own table, `inet setu`, drops inbound traffic to those ports on every interface except loopback. Even an app that binds `0.0.0.0` by mistake is reachable only through Caddy.

## Caddy is driven only through its socket

Setu never edits Caddy's files for routes. It talks to Caddy's admin API over a unix socket, `/run/caddy/admin.sock`, owned by group `caddy`. Caddy's TCP admin port, 2019, is turned off. That matters: anyone who can write to the admin API controls every route and certificate on the box. Site users are not in the `caddy` group, so a hosted app cannot reach it.

Setu only touches routes whose ids it wrote, `setu-site-<short>` and `setu-panel`. Any other route in Caddy is left alone.

## Routes repair themselves

The agent keeps a record of what it last applied, in `/var/lib/setu/state.json`: each site's domain and port. On start and every five minutes it reconciles Caddy against that record. Every site with a recorded domain gets its route back if missing, and `setu-site-*` routes for unknown sites are removed.

So if Caddy loses its saved configuration, the routes come back by themselves. Setu's end-to-end test deletes Caddy's autosave file, restarts `caddy-api`, and checks that both test sites are served again within 30 seconds.

## ACME or the internal CA

By default Caddy gets certificates through ACME, which is what you want for a public site. For a test box, or a server with no public DNS name yet, Caddy can issue from its own internal CA instead. You choose this at install time with `--tls internal`. Browsers then need to trust Caddy's root certificate:

```text
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

You can switch modes later without losing any site routes. Run `install-system` again with the new setting; it rewrites `/etc/caddy/setu.json` and applies it through the admin socket, keeping every site route:

```bash
# switch this server to ACME certificates
setu agent install-system --panel-host panel.example.com --upstream unix//run/setu/http.sock
# or to Caddy's internal CA
setu agent install-system --tls internal --panel-host panel.example.com --upstream unix//run/setu/http.sock
```

Leave out `--panel-host` and `--upstream` on servers that do not host the panel. On the control-plane box, also record the mode so the wizard's install command matches:

```bash
sudo -u setu setu setting set tls_internal true
```

## When HTTPS does not come up

Work through these in order:

1. **DNS.** Does the domain resolve to this server's public IP? Until it does, ACME cannot issue.
2. **Ports.** Are 80 and 443 open in any firewall in front of the server, including your provider's?
3. **The site.** Is it `running` in the panel? The route is only added once the health check passes.
4. **Caddy's log.** Certificate errors are logged by Caddy:

```bash
journalctl -u caddy-api
```

5. **The agent's own checks.** `setu agent doctor` confirms that `caddy-api.service` is active, the admin socket answers, nothing listens on `127.0.0.1:2019`, and the `inet setu` table is loaded.

## Next steps

If you want a CDN or proxy in front, see [putting Cloudflare in front of Setu](post:cloudflare-in-front-of-setu). Network rules and what sites share are part of [the Setu trust model](post:setu-trust-model). And if you have not created a site yet, [your first Vyasa site on Setu](post:first-vyasa-site-on-setu) takes you through it. TLS settings are also covered in [setucp.com/docs/operations](https://setucp.com/docs/operations).
