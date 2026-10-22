---
title: Running Setu behind Cloudflare: DNS, TLS and client IPs
seo_title: Setu behind Cloudflare: DNS, TLS and client IPs | Setu
seo_description: How to run Setu behind Cloudflare today: when to turn on the proxy, which SSL mode suits Caddy's certificates, the client IP caveat, and what 0.2 tunnels add.
keyphrase: Setu behind Cloudflare
excerpt: Setu's Caddy gets its own certificates, so Cloudflare's proxy is optional. If you want it, here is the order to turn it on, the SSL mode to pick, and the client-IP caveat to know.
category: Guides
tags: cloudflare, dns, tls, caddy, networking
cover_kicker: Networking guide
cover_alt: A diagram of a browser reaching Cloudflare, then Caddy on a Setu server, then a site on its loopback port
---
Many people already keep their DNS at Cloudflare, and some want its proxy in front of every site. Running Setu behind Cloudflare works, but a few choices matter: the order in which you enable the proxy, the SSL mode, and how client IP addresses reach your apps. This guide covers what works with Setu 0.1.x today, and what the 0.2 tunnel support is planned to change.

## How traffic reaches a Setu site today

Every Setu server runs Caddy on ports 80 and 443. Caddy gets a certificate for each site's domain through ACME (or from its own internal CA with `--tls internal`), redirects HTTP to HTTPS, and proxies each domain to its site on `127.0.0.1:<port>`. An nftables rule drops outside traffic to the site port range 20000–29999, so Caddy is the only way in.

That means Cloudflare is optional. A plain DNS record pointing at the server gives you working HTTPS with no proxy at all. Putting Cloudflare's proxy in front adds a hop: browser to Cloudflare, Cloudflare to Caddy, Caddy to the site.

## Step 1: start with DNS only

When you create a site, Setu adds Caddy's route and Caddy asks for a certificate. The simplest path is to let that first issuance happen with the record set to **DNS only** (the grey cloud), so the certificate authority reaches Caddy directly:

1. Create an `A` (and `AAAA` if you use IPv6) record for the domain, pointing at the server, proxy off.
2. Create the site in the panel (**New site → app → domain**) and wait for the job to finish.
3. Open `https://<domain>` and check the certificate is a real one from the ACME issuer.

If something goes wrong here, it is a plain DNS or port problem, and Caddy's journal says what failed:

```bash
journalctl -u caddy-api -n 100
```

The same steps, without Cloudflare, are in [custom domains and automatic HTTPS](post:custom-domains-automatic-https-caddy).

## Step 2: turn on the proxy, with Full (strict)

Once the site serves over HTTPS on its own, switch the record to **Proxied**. Then set the zone's SSL/TLS mode to **Full (strict)**. In that mode Cloudflare connects to your server over HTTPS and checks that the certificate is valid for the name, which it is, because Caddy holds a publicly trusted certificate for that domain.

Avoid **Flexible**. In that mode Cloudflare talks to the origin over plain HTTP, and Caddy answers plain HTTP with a redirect to HTTPS, which leads to a redirect loop.

Caddy keeps renewing its certificates on its own. If a renewal fails while the record is proxied, Caddy's journal shows the error, and switching the record back to DNS only while you look is a quick way to rule Cloudflare in or out.

### If the server uses `--tls internal`

A server installed with `--tls internal` gets certificates from Caddy's own CA, which Cloudflare does not trust. Full (strict) will then fail. Cloudflare's plain **Full** mode accepts an origin certificate it cannot verify, so it works, but it gives up the check that you are talking to your own server. On a server with a public IP, ACME plus Full (strict) is the better choice.

## Step 3: client IPs behind Cloudflare

This is the part that is easy to miss. Behind Cloudflare, the TCP connection that reaches Caddy comes from a Cloudflare address, not from the visitor.

The Caddy configuration Setu writes (`/etc/caddy/setu.json`) declares no trusted proxies. So Caddy forwards the address of the peer it sees, and behind the proxy that peer is Cloudflare. Your app then sees Cloudflare addresses as clients. For Vyasa, which trusts `127.0.0.1` (Caddy) through `VYASA_TRUSTED_PROXIES`, that affects anything keyed on client IP, such as rate limits and audit entries. Cloudflare sends the original visitor address in its own `CF-Connecting-IP` header; whether an app reads that is up to the app.

Do not fix this by hand-editing `/etc/caddy/setu.json`. Setu owns that file: `setu agent install-system` rewrites it, and the agent reconciles routes every five minutes.

## Keep the panel on DNS only

The panel has its own rules about client IPs. The login limiter allows 10 failed logins per client IP per 15 minutes, and every mutation is written to the audit log with the client IP. Behind a proxy, many visitors would share a few edge addresses in those records. The panel is also for operators, not the public, and agents reach it over HTTPS on their own.

Our recommendation: leave the panel's host (for example `panel.example.com`) as DNS only, and proxy only the sites that benefit from it.

![The New site dialog in the Setu panel, where the domain is entered](images/panel-new-site.png "The domain you enter here is the one Caddy requests a certificate for.")

## What 0.2 adds: Cloudflare tunnels

Cloudflare tunnel ingress is part of the approved 0.2 design. It is planned, not shipped. The design:

- A server can use `ingress = "tunnel"`. `setu agent install` installs `cloudflared` as a service with a per-server tunnel token, sealed on the control plane and written 0600 on the server.
- The agent manages one ingress rule per site, pointing at Caddy on `127.0.0.1:443`. Caddy keeps terminating TLS, with its internal CA on tunnel servers.
- DNS records are created through Cloudflare's API with a zone-scoped token you enter once in Settings, or printed as the `CNAME` to add by hand.
- Reconcile covers tunnel rules like Caddy routes, and `doctor` checks the tunnel is connected.

The point is servers without a public IP: they would join and serve sites through the tunnel alone. Site moves in the same release benefit too, because when both servers sit behind the same tunnel, DNS does not change. The [roadmap post](post:setu-roadmap) has the rest of 0.2.

## Next steps

- Read what the firewall and Caddy rules cover in the [security docs](https://setucp.com/docs/security).
- Lock down the rest of the host with [hardening an Ubuntu server for Setu](post:hardening-ubuntu-for-setu).
- Not installed yet? Start at [setucp.com/install](https://setucp.com/install).
